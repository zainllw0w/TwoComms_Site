# Rollout and Deploy Brief

## 1. Rollout phases
1. Phase 0: Data contracts and feature flags.
2. Phase 1: Score engine shadow mode (без влияния на UI decisions).
3. Phase 2: Manager/admin dashboard integration.
4. Phase 3: Alerts and advice automation.
5. Phase 4: DTF read-only bridge v1.

## 2. Feature flags
- `management_score_v2_enabled`
- `management_trust_layer_enabled`
- `management_alerts_v2_enabled`
- `management_dtf_bridge_v1_enabled`

## 3. Deployment checklist
1. Migrations applied.
2. Scheduler jobs registered.
3. Single beat instance verified.
4. Alert dedupe storage verified.
5. Admin digest and no-report flow smoke-tested.
6. DTF bridge fallback tested.

## 4. Post-deploy monitoring
1. Score generation success rate.
2. Alert delivery success rate.
3. Duplicate alert incidents.
4. Trust critical spike count.
5. DTF bridge availability.

## 5. Rollback criteria
1. Incorrect score computation affecting payroll decisions.
2. Massive alert duplication.
3. Role-based data leakage.
4. DTF bridge causing dashboard instability.

## 6. Rollback path
1. Disable v2 flags.
2. Return to existing stats pipeline.
3. Keep data snapshots for forensic comparison.
