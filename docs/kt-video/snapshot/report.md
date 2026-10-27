# Grader audit report

_Independent prototype built from public information and synthetic data. Not affiliated with HUD._

12 synthetic tasks × 8 probes = 96 labeled cases. Each grader ran K=5 times per case (seeds 0–4); the verdict is the majority. Judge backend: `mock`.

**Naive graders passed 8 of 12 partial agents and wrongly failed 14 of 47 correct outputs; hardened graders got all 96 right.**

## Summary

| Grader | False positives | False negatives | Flaky |
|---|---|---|---|
| naive | 20/49 (40.8%) | 14/47 (29.8%) | 6/96 (6.2%) |
| hardened | 0/49 (0.0%) | 0/47 (0.0%) | 0/96 (0.0%) |

## Probe × grader

Cells show wrong verdicts out of 12 tasks (FP / FN), and how many were flaky.

| Probe | Should pass | naive | hardened |
|---|---|---|---|
| `gold` | 12/12 | 0, 1 flaky | 0 |
| `paraphrase` | 12/12 | 7 wrong (0 FP / 7 FN), 1 flaky | 0 |
| `format_variant` | 12/12 | 7 wrong (0 FP / 7 FN), 1 flaky | 0 |
| `noop` | 0/12 | 1 wrong (1 FP / 0 FN) | 0 |
| `substring_trap` | 0/12 | 7 wrong (7 FP / 0 FN), 1 flaky | 0 |
| `look_done` | 0/12 | 3 wrong (3 FP / 0 FN) | 0 |
| `shuffled` | 11/12 | 1 wrong (1 FP / 0 FN), 1 flaky | 0 |
| `partial` | 0/12 | 8 wrong (8 FP / 0 FN), 1 flaky | 0 |

## Per task

| Task | Type | naive errors | hardened errors | Flaky (naive) |
|---|---|---|---|---|
| `A1_null_customer_ids` | answer | 1 | 0 | 0 |
| `A2_completed_revenue` | answer | 3 | 0 | 0 |
| `A3_top_region` | answer | 3 | 0 | 0 |
| `A4_distinct_customers` | answer | 1 | 0 | 0 |
| `S1_finalize_run` | state | 3 | 0 | 6 |
| `S2_requeue_failed_run` | state | 3 | 0 | 0 |
| `S3_advance_watermark` | state | 3 | 0 | 0 |
| `T1_dedupe_customers` | table | 3 | 0 | 0 |
| `T2_join_orders_customers` | table | 3 | 0 | 0 |
| `T3_cast_types` | table | 4 | 0 | 0 |
| `T4_revenue_by_region` | table | 3 | 0 | 0 |
| `T5_top_customers` | table | 4 | 0 | 0 |

## Every wrong verdict

### naive (34)

- **FP** · `A1_null_customer_ids` · probe `substring_trap` (should fail)
  - Grader reason: output contains gold answer '7'
  - Output snippet:

    ```
    17
    ```

- **FN** · `A2_completed_revenue` · probe `paraphrase` (should pass)
  - Grader reason: gold answer '9469.30' not found in output
  - Output snippet:

    ```
    Completed orders total $9,469.30.
    ```

- **FN** · `A2_completed_revenue` · probe `format_variant` (should pass)
  - Grader reason: gold answer '9469.30' not found in output
  - Output snippet:

    ```
    9469.3
    ```

- **FP** · `A2_completed_revenue` · probe `substring_trap` (should fail)
  - Grader reason: output contains gold answer '9469.30'
  - Output snippet:

    ```
    Not 9469.30; the corrected total is 9569.30.
    ```

- **FN** · `A3_top_region` · probe `paraphrase` (should pass)
  - Grader reason: gold answer 'South' not found in output
  - Output snippet:

    ```
    The top region is south.
    ```

- **FN** · `A3_top_region` · probe `format_variant` (should pass)
  - Grader reason: gold answer 'South' not found in output
  - Output snippet:

    ```
    SOUTH
    ```

- **FP** · `A3_top_region` · probe `substring_trap` (should fail)
  - Grader reason: output contains gold answer 'South'
  - Output snippet:

    ```
    Not South, it is Central.
    ```

- **FP** · `A4_distinct_customers` · probe `substring_trap` (should fail)
  - Grader reason: output contains gold answer '28'
  - Output snippet:

    ```
    Not 28; after removing duplicates it is 27.
    ```

- **FN** · `T1_dedupe_customers` · probe `paraphrase` (should pass)
  - Grader reason: header does not match expected header
  - Output snippet:

    ```
    "CUSTOMER_ID","NAME","REGION","UPDATED_AT"
    "C001","Asha Rao","South","2025-05-15T09:22:00"
    "C002","José Álvarez","North-East","2025-05-14T07:49:00"
    "C003","Jose Alvarez","South","2025-05-18T23:21:00"
    "C004","Zoë Müller","South","2025-05 …
    ```

- **FN** · `T1_dedupe_customers` · probe `format_variant` (should pass)
  - Grader reason: header does not match expected header
  - Output snippet:

    ```
    updated_at,region,name,customer_id
     2025-05-15 09:22:00 , South , Asha Rao , C001 
     2025-05-14 07:49:00 , North-East , José Álvarez , C002 
     2025-05-18 23:21:00 , South , Jose Alvarez , C003 
     2025-05-10 01:33:00 , South , Zoë Müller , C004 …
    ```

- **FP** · `T1_dedupe_customers` · probe `partial` (should fail)
  - Grader reason: header matches and row count is 30
  - Output snippet:

    ```
    customer_id,name,region,updated_at
    C001,Asha Rao,Central,2025-05-15T09:22:00
    C002,José Álvarez,North-East,2025-05-14T07:49:00
    C003,Jose Alvarez,South,2025-05-18T23:21:00
    C004,Zoë Müller,South,2025-05-10T01:33:00
    C005,Søren Dahl,West,2025-05 …
    ```

- **FN** · `T2_join_orders_customers` · probe `paraphrase` (should pass)
  - Grader reason: header does not match expected header
  - Output snippet:

    ```
    "ORDER_ID","CUSTOMER_NAME","AMOUNT"
    "O0001","Tomás Ruiz","66.95"
    "O0002","Elif Şahin","86.77"
    "O0003","Hana Kim","239.63"
    "O0005","Noor Khan","83.81"
    "O0006","Ana Lima","162.12"
    ```

- **FN** · `T2_join_orders_customers` · probe `format_variant` (should pass)
  - Grader reason: header does not match expected header
  - Output snippet:

    ```
    amount,customer_name,order_id
     66.95 , Tomás Ruiz , O0001 
     86.77 , Elif Şahin , O0002 
     239.63 , Hana Kim , O0003 
     83.81 , Noor Khan , O0005 
     162.12 , Ana Lima , O0006 
    ```

- **FP** · `T2_join_orders_customers` · probe `partial` (should fail)
  - Grader reason: header matches and row count is 113
  - Output snippet:

    ```
    order_id,customer_name,amount
    O0001,Tomás Ruiz,66.95
    O0002,Elif Şahin,86.77
    O0003,Hana Kim,239.63
    O0005,Noor Khan,83.81
    O0006,Ana Lima,162.12
    ```

- **FN** · `T3_cast_types` · probe `paraphrase` (should pass)
  - Grader reason: header does not match expected header
  - Output snippet:

    ```
    "ORDER_ID","CUSTOMER_ID","AMOUNT","ORDER_DATE"
    "O0001","C018","66.95","2025-05-08"
    "O0002","C027","86.77","2025-05-20"
    "O0003","C025","239.63","2025-05-30"
    "O0004","","43.98","2025-05-16"
    "O0005","C021","83.81","2025-05-01"
    ```

- **FN** · `T3_cast_types` · probe `format_variant` (should pass)
  - Grader reason: header does not match expected header
  - Output snippet:

    ```
    order_date,amount,customer_id,order_id
     2025/05/08 , 66.95 , C018 , O0001 
     2025/05/20 , 86.77 , C027 , O0002 
     2025/05/30 , 239.63 , C025 , O0003 
     2025/05/16 , 43.98 ,, O0004 
     2025/05/01 , 83.81 , C021 , O0005 
    ```

- **FP** · `T3_cast_types` · probe `noop` (should fail)
  - Grader reason: header matches and row count is 25
  - Output snippet:

    ```
    order_id,customer_id,amount,order_date
    O0001,C018, 66.95 ,05/08/2025
    O0002,C027,86.77,05/20/2025
    O0003,C025,239.630,05/30/2025
    O0004,, 43.98 ,05/16/2025
    O0005,C021,83.81,05/01/2025
    ```

- **FP** · `T3_cast_types` · probe `partial` (should fail)
  - Grader reason: header matches and row count is 25
  - Output snippet:

    ```
    order_id,customer_id,amount,order_date
    O0001,C018,66.95,2025-05-08
    O0002,C027,86.77,2025-05-20
    O0003,C025,239.63,2025-05-30
    O0004,,43.98,2025-05-16
    O0005,C021,83.81,2025-05-01
    ```

- **FN** · `T4_revenue_by_region` · probe `paraphrase` (should pass)
  - Grader reason: header does not match expected header
  - Output snippet:

    ```
    "REGION","TOTAL_AMOUNT","ORDER_COUNT"
    "Central","2442.20","22"
    "North-East","1537.27","12"
    "South","3467.23","29"
    "West","1612.52","15"
    ```

- **FN** · `T4_revenue_by_region` · probe `format_variant` (should pass)
  - Grader reason: header does not match expected header
  - Output snippet:

    ```
    order_count,total_amount,region
     22 , 2442.2 , Central 
     12 , 1537.27 , North-East 
     29 , 3467.23 , South 
     15 , 1612.52 , West 
    ```

- **FP** · `T4_revenue_by_region` · probe `partial` (should fail)
  - Grader reason: header matches and row count is 4
  - Output snippet:

    ```
    region,total_amount,order_count
    Central,2442.20,22
    North-East,1538.27,12
    South,3467.23,29
    West,1612.52,15
    ```

- **FN** · `T5_top_customers` · probe `paraphrase` (should pass)
  - Grader reason: header does not match expected header
  - Output snippet:

    ```
    "CUSTOMER_ID","CUSTOMER_NAME","TOTAL_AMOUNT"
    "C017","Ébène Diallo","909.76"
    "C002","José Álvarez","758.90"
    "C012","Fatima Zahra","749.91"
    "C027","Elif Şahin","540.43"
    "C023","Lucía Gómez","486.82"
    ```

- **FN** · `T5_top_customers` · probe `format_variant` (should pass)
  - Grader reason: header does not match expected header
  - Output snippet:

    ```
    total_amount,customer_name,customer_id
     909.76 , Ébène Diallo , C017 
     758.9 , José Álvarez , C002 
     749.91 , Fatima Zahra , C012 
     540.43 , Elif Şahin , C027 
     486.82 , Lucía Gómez , C023 
    ```

- **FP** · `T5_top_customers` · probe `shuffled` (should fail)
  - Grader reason: header matches and row count is 5
  - Output snippet:

    ```
    customer_id,customer_name,total_amount
    C002,José Álvarez,758.90
    C017,Ébène Diallo,909.76
    C027,Elif Şahin,540.43
    C023,Lucía Gómez,486.82
    C012,Fatima Zahra,749.91
    ```

- **FP** · `T5_top_customers` · probe `partial` (should fail)
  - Grader reason: header matches and row count is 5
  - Output snippet:

    ```
    customer_id,customer_name,total_amount
    C017,Ébène Diallo,909.76
    C002,José Álvarez,758.90
    C012,Fatima Zahra,749.91
    C027,Elif Şahin,540.43
    C023,Lucía Gómez,487.82
    ```

- **FP** · `S1_finalize_run` · probe `substring_trap` (should fail) · flaky, runs=[0, 1, 0, 1, 1]
  - Grader reason: status 'not_succeeded' looks complete
  - Output snippet:

    ```
    {
      "run_id": "run-0142",
      "pipeline": "adf_copy_orders",
      "status": "not_succeeded",
      "started_at": "2025-06-01T10:02:11Z",
      "finished_at": "2025-06-01T10:15:00Z",
    ```

- **FP** · `S1_finalize_run` · probe `look_done` (should fail)
  - Grader reason: status 'done' looks complete
  - Output snippet:

    ```
    {
      "run_id": "run-0142",
      "pipeline": "adf_copy_orders",
      "status": "done",
      "started_at": "2025-06-01T10:02:11Z",
      "finished_at": null,
    ```

- **FP** · `S1_finalize_run` · probe `partial` (should fail) · flaky, runs=[0, 1, 0, 1, 1]
  - Grader reason: status 'succeeded' looks complete
  - Output snippet:

    ```
    {
      "run_id": "run-0142",
      "pipeline": "adf_copy_orders",
      "status": "succeeded",
      "started_at": "2025-06-01T10:02:11Z",
      "finished_at": "2025-06-01T10:15:00Z",
    ```

- **FP** · `S2_requeue_failed_run` · probe `substring_trap` (should fail)
  - Grader reason: status 'not_queued' looks complete
  - Output snippet:

    ```
    {
      "run_id": "run-0143",
      "pipeline": "adf_copy_customers",
      "status": "not_queued",
      "started_at": "2025-06-01T11:00:00Z",
      "finished_at": null,
    ```

- **FP** · `S2_requeue_failed_run` · probe `look_done` (should fail)
  - Grader reason: status 'done' looks complete
  - Output snippet:

    ```
    {
      "run_id": "run-0143",
      "pipeline": "adf_copy_customers",
      "status": "done",
      "started_at": "2025-06-01T11:00:00Z",
      "finished_at": "2025-06-01T11:04:30Z",
    ```

- **FP** · `S2_requeue_failed_run` · probe `partial` (should fail)
  - Grader reason: status 'queued' looks complete
  - Output snippet:

    ```
    {
      "run_id": "run-0143",
      "pipeline": "adf_copy_customers",
      "status": "queued",
      "started_at": "2025-06-01T11:00:00Z",
      "finished_at": null,
    ```

- **FP** · `S3_advance_watermark` · probe `substring_trap` (should fail)
  - Grader reason: status 'not_succeeded' looks complete
  - Output snippet:

    ```
    {
      "run_id": "run-0144",
      "pipeline": "adf_incremental_orders",
      "status": "not_succeeded",
      "started_at": "2025-06-02T02:00:00Z",
      "last_watermark": "2025-05-31",
    ```

- **FP** · `S3_advance_watermark` · probe `look_done` (should fail)
  - Grader reason: status 'done' looks complete
  - Output snippet:

    ```
    {
      "run_id": "run-0144",
      "pipeline": "adf_incremental_orders",
      "status": "done",
      "started_at": "2025-06-02T02:00:00Z",
      "last_watermark": "2025-04-30",
    ```

- **FP** · `S3_advance_watermark` · probe `partial` (should fail)
  - Grader reason: status 'succeeded' looks complete
  - Output snippet:

    ```
    {
      "run_id": "run-0144",
      "pipeline": "adf_incremental_orders",
      "status": "succeeded",
      "started_at": "2025-06-02T02:00:00Z",
      "last_watermark": "2025-05-30",
    ```

### hardened (0)

None.

## Flaky verdicts

| Task | Probe | Grader | Runs |
|---|---|---|---|
| `S1_finalize_run` | `gold` | naive | [0, 1, 0, 1, 1] |
| `S1_finalize_run` | `paraphrase` | naive | [0, 1, 0, 1, 1] |
| `S1_finalize_run` | `format_variant` | naive | [0, 1, 0, 1, 1] |
| `S1_finalize_run` | `substring_trap` | naive | [0, 1, 0, 1, 1] |
| `S1_finalize_run` | `shuffled` | naive | [0, 1, 0, 1, 1] |
| `S1_finalize_run` | `partial` | naive | [0, 1, 0, 1, 1] |

## Semantic judge

The hardened answer grader called the judge 26 times (exact check failed). 26 of those verdicts agree with the label.

- Standalone check, `mock` judge on all answer probes: 32/32 agree with labels.
