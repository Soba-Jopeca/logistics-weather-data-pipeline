# Versões utilizadas no laboratório do curso.
ARG AIRFLOW_VERSION=2.9.2
ARG PYTHON_VERSION=3.10

FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}

# Disponibiliza o argumento nesta etapa de construção.
ARG AIRFLOW_VERSION

ENV AIRFLOW_HOME=/opt/airflow

USER airflow

COPY --chown=airflow:root requirements.txt /requirements.txt

RUN pip install --no-cache-dir \
        "apache-airflow==${AIRFLOW_VERSION}" \
        "apache-airflow-providers-docker==3.13.0" \
        -r /requirements.txt \
        && pip check