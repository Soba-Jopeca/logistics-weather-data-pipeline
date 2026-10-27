"""Read-only identity checks. Attestations are evidence, not OS sandboxes."""
import hashlib
import json
import re
from pathlib import Path

BASELINE = '70b02b044e36adaa0a29612da87cf8bf688567c9'
BASELINE_HASHES = {'config/locations.json': '06a4e066299c95f0d0fe4088f356f46956da03f1b1c6354192dd1216cfcf9ce9', 'dags/weather_extract.py': '37e22cd3c007f10517e609cf9a5d27f3091b73c4fbd1366736145d7a34d19568', 'scripts/__init__.py': '39b8b54456db15e299ac15aab252ef56e16ff3375803da2aea7b64819b9840ec', 'scripts/extract_weather.py': '1bd23fec467ecf9523b8a7973519e26c5721bd2c519913275d596e93373c0b84', 'scripts/weather_daily.py': 'eb81b40ce0228fc484034e96d12cc6f2c75322ca5c776d6548c346abb423c920', 'scripts/weather_interface.py': '1b589c0cfb1ab01465634ac34d97fcf3e121f35dc4b87c0533a7b79095ebc49c', 'scripts/weather_manifest.py': '679a26233c7647967de42a3c16fd1e2373f12f31b218386fef6862ccc845c74f', 'scripts/weather_slots.py': '48399aa1249602c462655b027419d2c0a170ffc173ee441ad08f6866008e73bb', 'scripts/weather_temporal.py': '14fb428e0c417da942905d82ff14d96c49d194c7129da4bba88f2803fd475112', 'scripts/weather_window.py': '5a3bccf919c59444e84594d608f4eb8a260bdb6cc6a229bbdcd497b4642738d8'}
LIMITS = {'B01': (2, 5), 'B02': (1, 5), 'B03': (1, 7), 'B04': (1, 5),
          'B05': (1, 0), 'B06': (2, 0), 'B07': (1, 0), 'B08': (1, 5),
          'B09': (1, 0), 'B10': (2, 5), 'C01': (1, 5), 'C02': (1, 0)}

class GateError(RuntimeError):
    """Fail closed: never fall through to live execution."""

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()

def source_digest(path):
    """Hash text sources consistently across LF and Windows CRLF checkouts."""
    content = Path(path).read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(content).hexdigest()

def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise GateError('Duplicate JSON key')
            result[key] = value
        return result
    try:
        return json.loads(Path(path).read_text(), object_pairs_hook=unique)
    except (OSError, ValueError) as exc:
        raise GateError('Unreadable control document') from exc

def contained(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if path == root or root not in path.parents:
        raise GateError('Path outside exclusive root')
    return path

def validate_campaign(doc):
    required = {'schema_version', 'campaign_id', 'baseline', 'enabled', 'root',
                'code_root', 'hashes', 'scenarios', 'slots', 'authorization'}
    if set(doc) != required or doc['schema_version'] != 1 or doc['baseline'] != BASELINE:
        raise GateError('Campaign schema/baseline mismatch')
    if type(doc['enabled']) is not bool or not re.fullmatch(r'p09e3_[a-z0-9_]{8,64}', doc['campaign_id']):
        raise GateError('Campaign identity invalid')
    root, code = Path(doc['root']), Path(doc['code_root'])
    if not root.is_absolute() or not code.is_absolute():
        raise GateError('Absolute paths required')
    if root.resolve() == code.resolve() or code.resolve() in root.resolve().parents or root.resolve() in code.resolve().parents:
        raise GateError('Campaign and code roots must be disjoint')
    if not isinstance(doc['hashes'], dict) or not doc['hashes']:
        raise GateError('Missing pinned source hashes')
    for name, sha in doc['hashes'].items():
        contained(code, code / name)
        if not re.fullmatch('[0-9a-f]{64}', sha):
            raise GateError('Invalid source hash')
    if not isinstance(doc['scenarios'], list) or len(set(doc['scenarios'])) != len(doc['scenarios']) or not set(doc['scenarios']) <= set(LIMITS):
        raise GateError('Invalid scenarios')
    if not isinstance(doc['slots'], list) or len(doc['slots']) > 2:
        raise GateError('At most two scheduled slots')
    if not isinstance(doc['authorization'], str):
        raise GateError('Authorization must be a reference')
    return doc

def inspect_baseline(doc):
    """All authored execution modules must be pinned; no Git subprocess."""
    validate_campaign(doc)
    root = Path(doc['code_root'])
    if doc['hashes'] != BASELINE_HASHES:
        raise GateError('Manifest differs from pinned approved baseline')
    required = {'dags/weather_extract.py', 'config/locations.json'} | {
        p.relative_to(root).as_posix() for p in (root / 'scripts').glob('*.py')}
    if not required <= set(doc['hashes']) or not (root / 'scripts/weather_daily.py').is_file():
        raise GateError('Incomplete source inventory')
    for name, sha in doc['hashes'].items():
        path = contained(root, root / name)
        if source_digest(path) != sha:
            raise GateError('Source hash mismatch: ' + name)
    return digest(doc['hashes'])

def verify_mount_identity(host_root, container_root, relative, expected_sha256):
    paths = [contained(root, Path(root) / relative) for root in (host_root, container_root)]
    if any(hashlib.sha256(p.read_bytes()).hexdigest() != expected_sha256 for p in paths):
        raise GateError('Shared-root witness mismatch')
    # Same content is only a visibility witness; atomicity requires block A.
    return {'visibility': True, 'atomicity_proven': False}

def require_gate(doc, evidence, *, participant):
    validate_campaign(doc)
    if not doc['enabled'] or not doc['authorization'].strip():
        raise GateError('Operational campaign not authorized')
    expected = {'campaign_sha256': digest(doc), 'external_network_blocked': True,
                'operational_mounts_absent': True, 'exclusive_metadata': True,
                'write_confinement': True, 'shared_root_verified': True}
    if any(evidence.get(k) != v for k, v in expected.items()):
        raise GateError('Isolation evidence incomplete or for another campaign')
    if participant == 'windows' and evidence.get('windows_acl_and_firewall_verified') is not True:
        raise GateError('Windows confinement unproven')
    if participant not in {'windows', 'docker'}:
        raise GateError('Unknown participant')
    inspect_baseline(doc)
    return digest(evidence)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Read-only E3 gate; never starts services')
    parser.add_argument('--campaign', required=True)
    parser.add_argument('--evidence', required=True)
    args = parser.parse_args()
    doc, evidence = read_json(args.campaign), read_json(args.evidence)
    require_gate(doc, evidence, participant='docker')
    print('Isolation evidence checked; no service started. Explicit operational authorization required.')


if __name__ == '__main__':
    main()
