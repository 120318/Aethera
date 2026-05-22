# Summary

Describe the change and the user-visible behavior it affects.

## Type of change

- [ ] Bug fix
- [ ] Feature
- [ ] Refactor
- [ ] Documentation
- [ ] Configuration or deployment
- [ ] Other

## Impact

- User-visible behavior:
- Configuration or migration impact:
- External services affected:
- Risk areas:

## Verification

List the exact checks you ran.

```bash
./scripts/review_with_gates.sh
```

## Checklist

- [ ] I kept the change focused.
- [ ] I updated documentation when behavior, setup, or configuration changed.
- [ ] I verified the change through Docker-based commands.
- [ ] I ran `./scripts/review_with_gates.sh`, or explained why it could not run.
- [ ] Backend changes follow `docs/backend-contracts.md` and `docs/backend-architecture.md`.
- [ ] Frontend changes follow `docs/frontend-contracts.md` and `docs/frontend-architecture.md`.
- [ ] I did not add secrets, local config, logs, cache files, databases, or media files.
