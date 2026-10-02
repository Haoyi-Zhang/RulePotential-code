# Casbin example policy records

These three small policy fixtures were read from the public Casbin repository
on 11 September 2026 and transcribed from the web tool's readable raw-file
view, preserving all records and the displayed blank line. The consumed
files are retained here. They are not claimed byte-identical to an upstream
Git object: transport through this environment did not supply original bytes,
and a final newline is normalized in each consumed file.

- https://raw.githubusercontent.com/casbin/casbin/master/examples/rbac_policy.csv
- https://raw.githubusercontent.com/casbin/casbin/master/examples/rbac_with_domains_policy.csv
- https://raw.githubusercontent.com/casbin/casbin/master/examples/rbac_with_resource_roles_policy.csv
- Upstream license: https://raw.githubusercontent.com/casbin/casbin/master/LICENSE

Casbin is distributed under Apache License 2.0; see ../../licenses/Apache-2.0.txt.
No Casbin implementation is executed, copied, or modified. The new adapter
interprets these example records in the explicitly documented positive Horn
policy fragment; it is not a conformance test of the complete Casbin engine.
All temporal annotations and update schedules are generated for this study,
not observed access events. Example names are upstream toy identifiers.
