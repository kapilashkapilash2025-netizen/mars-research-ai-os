# ADR 0005: Reviewed eight-wheel Safety Motion Controller

Navigation cannot create HAL commands because command authority must validate freshness, review, limits,
state and all eight outcomes in one place. Authorization and human review are separate; neither defeats
e-stop, critical fault, stale data or hard limits. Old commands never resume after e-stop clear. Initial
skid-steer kinematics are simulation approximations. Conservative rejection is preferred to unsupported
degraded mobility. This deterministic controller is not hardware-ready.
