"""Política diária pura. Não ativa agenda nem executa coleta."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


TIMEZONE_NAME = "America/Sao_Paulo"
POLICY_VERSION = "daily-v1"
LOCATION_IDS = frozenset({
    "br_sp_campinas", "br_sp_sao_paulo", "br_sp_sorocaba",
    "br_sp_jundiai", "br_sp_ribeirao_preto",
})


def aware_utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("O instante deve ser datetime com timezone.")
    if value.utcoffset() is None:
        raise ValueError("O instante deve possuir offset definido.")
    return value.astimezone(timezone.utc)


def utc_text(value):
    return aware_utc(value).isoformat().replace("+00:00", "Z")


def parse_instant(value):
    if not isinstance(value, str):
        raise ValueError("O instante persistido deve ser texto.")
    try:
        parsed = datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value
        )
    except ValueError as error:
        raise ValueError("Instante persistido inválido.") from error
    return aware_utc(parsed)


def _cycle(value):
    if type(value) is date:
        return value
    if isinstance(value, str):
        parsed = date.fromisoformat(value)
        if parsed.isoformat() == value:
            return parsed
    raise ValueError("cycle_date deve ser data ou texto AAAA-MM-DD.")


def _local_instant(day, hour, minute):
    return datetime.combine(
        day, time(hour, minute), tzinfo=ZoneInfo(TIMEZONE_NAME)
    ).astimezone(timezone.utc)


@dataclass(frozen=True)
class DailySlot:
    cycle_date: date
    scheduled_slot: datetime

    def __post_init__(self):
        if type(self.cycle_date) is not date:
            raise ValueError("Ciclo inválido.")
        actual = aware_utc(self.scheduled_slot)
        if actual != _local_instant(self.cycle_date, 13, 45):
            raise ValueError("Slot diferente de D 13h45 em America/Sao_Paulo.")
        object.__setattr__(self, "scheduled_slot", actual)

    @property
    def admission_end(self):
        return _local_instant(self.cycle_date, 14, 0)

    @property
    def readiness_cutoff(self):
        return _local_instant(self.cycle_date, 14, 15)

    @property
    def intended_consumption(self):
        return _local_instant(self.cycle_date, 14, 30)


def resolve_daily_slot(
    *, source, cycle_date=None, data_interval_start=None, data_interval_end=None
):
    """Scheduled usa intervalo diário; manual/CLI exigem D explícito."""
    if source in {"manual", "cli"}:
        if data_interval_start is not None or data_interval_end is not None:
            raise ValueError("Execução manual não seleciona D pelo intervalo.")
        day = _cycle(cycle_date)
        return DailySlot(day, _local_instant(day, 13, 45))

    if source != "scheduled":
        raise ValueError("Origem de execução não suportada.")
    end = aware_utc(data_interval_end)
    start = aware_utc(data_interval_start)
    # Airflow usa Pendulum; normalizar sua subclasse Date para o contrato puro.
    day = date.fromisoformat(end.astimezone(ZoneInfo(TIMEZONE_NAME)).date().isoformat())
    slot = DailySlot(day, end)
    # Subtrair uma data local, não assumir duração UTC fixa em transições de fuso.
    if start != _local_instant(day - timedelta(days=1), 13, 45):
        raise ValueError("Intervalo incompatível com a timetable diária.")
    if cycle_date is not None and _cycle(cycle_date) != day:
        raise ValueError("cycle_date diverge do slot agendado.")
    return slot


def evaluate_admission(slot, now):
    if not isinstance(slot, DailySlot):
        raise ValueError("Slot inválido.")
    instant = aware_utc(now)
    if instant < slot.scheduled_slot:
        reason = "too_early"
    elif instant > slot.admission_end:
        reason = "start_expired"
    else:
        reason = None
    return {
        "eligible": reason is None,
        "reason": reason,
        "observed_at": utc_text(instant),
        "delay_seconds": (instant - slot.scheduled_slot).total_seconds(),
    }


class DailyAdmissionError(RuntimeError):
    """Não deve ser absorvida como falha meteorológica de uma cidade."""

    def __init__(self, decision):
        self.decision = decision
        super().__init__(decision["reason"])


class FirstTransportGuard:
    """Uma instância por rodada; nunca reutilizar em outra execução.

    O adaptador chama antes de requests.get. Esta classe não autoriza coleta
    isoladamente e não substitui claim/dispatch.
    """

    def __init__(self, slot, clock):
        self.slot = slot
        self.clock = clock
        self.started_at = None
        self._failure = None

    def __call__(self):
        if self._failure is not None:
            raise DailyAdmissionError(dict(self._failure))
        if self.started_at is None:
            decision = evaluate_admission(self.slot, self.clock())
            if not decision["eligible"]:
                self._failure = decision
                raise DailyAdmissionError(dict(decision))
            self.started_at = decision["observed_at"]


def evaluate_freshness(collected_at_by_city, consumed_at):
    """Mede idade da resposta, não idade/precisão do modelo meteorológico."""
    instant = aware_utc(consumed_at)
    if (
        not isinstance(collected_at_by_city, dict)
        or set(collected_at_by_city) != LOCATION_IDS
    ):
        raise ValueError("Frescor exige exatamente as cinco localidades.")
    ages = {}
    reasons = set()
    for city in sorted(LOCATION_IDS):
        value = collected_at_by_city[city]
        try:
            collected = parse_instant(value) if isinstance(value, str) else aware_utc(value)
            age = (instant - collected).total_seconds()
        except (TypeError, ValueError, OverflowError):
            ages[city] = None
            reasons.add("invalid_timestamp")
            continue
        ages[city] = age
        if age < 0:
            reasons.add("invalid_timestamp")
        elif age > 3600:
            reasons.add("stale_collection")
    valid = [age for age in ages.values() if age is not None and age >= 0]
    return {
        "eligible": not reasons,
        "reasons": sorted(reasons),
        "consumed_at": utc_text(instant),
        "ages_seconds": ages,
        "oldest_age_seconds": max(valid) if valid else None,
        "spread_seconds": max(valid) - min(valid) if len(valid) == 5 else None,
        "nominal_age_seconds": 2700,
        "maximum_age_seconds": 3600,
    }
