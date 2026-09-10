import sys; sys.path.insert(0, '.')
from backend.telemetry.service import telemetry_service

states = telemetry_service.tick()
print('Machines ticked:', list(states.keys()))

m = states['M-003']
rs = m['risk_score']
rl = m['risk_level']
temp = m['temperature']
factors = [f['name'] for f in m['risk_factors']]
print(f'M-003: risk={rs:.1f} ({rl}), temp={temp:.1f}C')
print(f'  Factors: {factors}')

summary = telemetry_service.get_facility_summary()
print(f'Facility safety score: {summary["facility_safety_score"]}')
print(f'Total machines: {summary["total_machines"]}')
print('Telemetry service OK')
