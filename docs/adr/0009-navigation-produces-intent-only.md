# ADR 0009: Navigation produces intent only

Navigation cannot create HAL or motor commands or modify Twin state. Immutable intents preserve the
Safety Motion Controller authority boundary and make planning deterministic/testable.
