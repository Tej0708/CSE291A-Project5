# Trace timelines

All times are milliseconds from each logical run start. Event IDs identify exact trace records.

## 01_BASE-0004-NONE__unprotected

| ms | Attempt | Iteration | Event | Evidence |
|---:|---:|---:|---|---|
| 1312.7 | 1 | 1 | router_selection | app_crash; `419bce61-c20d-45bc-ab9e-eced1c81c43d:6` |
| 1814.7 | 1 | 1 | helper_accepted | app_crash; `419bce61-c20d-45bc-ab9e-eced1c81c43d:18` |
| 2180.7 | 1 | 2 | router_selection | incorrect_invoice; `419bce61-c20d-45bc-ab9e-eced1c81c43d:24` |
| 2537.4 | 1 | 2 | helper_accepted | incorrect_invoice; `419bce61-c20d-45bc-ab9e-eced1c81c43d:36` |
| 2538.0 | 1 | 2 | attempt_finished | completed; `419bce61-c20d-45bc-ab9e-eced1c81c43d:40` |

## 02_BASE-0004-NONE__full_restart

| ms | Attempt | Iteration | Event | Evidence |
|---:|---:|---:|---|---|
| 313.1 | 1 | 1 | router_selection | app_crash; `83507e42-c971-44b6-9922-02f7cb7c7686:6` |
| 717.6 | 1 | 1 | helper_accepted | app_crash; `83507e42-c971-44b6-9922-02f7cb7c7686:18` |
| 926.3 | 1 | 2 | router_selection | incorrect_invoice; `83507e42-c971-44b6-9922-02f7cb7c7686:24` |
| 1200.3 | 1 | 2 | helper_accepted | incorrect_invoice; `83507e42-c971-44b6-9922-02f7cb7c7686:36` |
| 1202.9 | 1 | 2 | attempt_finished | completed; `83507e42-c971-44b6-9922-02f7cb7c7686:50` |

## 03_BASE-0004-NONE__always_verify

| ms | Attempt | Iteration | Event | Evidence |
|---:|---:|---:|---|---|
| 188.0 | 1 | 1 | router_selection | app_crash; `eacac8df-889c-412d-b221-32d248eca9c8:6` |
| 671.5 | 1 | 1 | helper_accepted | app_crash; `eacac8df-889c-412d-b221-32d248eca9c8:23` |
| 981.2 | 1 | 2 | router_selection | incorrect_invoice; `eacac8df-889c-412d-b221-32d248eca9c8:32` |
| 1387.8 | 1 | 2 | helper_accepted | incorrect_invoice; `eacac8df-889c-412d-b221-32d248eca9c8:49` |
| 1388.8 | 1 | 2 | attempt_finished | completed; `eacac8df-889c-412d-b221-32d248eca9c8:56` |

## 04_BASE-0004-QA_CORRUPTION__unprotected

| ms | Attempt | Iteration | Event | Evidence |
|---:|---:|---:|---|---|
| 218.6 | 1 | 1 | router_selection | app_crash; `b0713e2a-90a2-4bdc-a284-15dd50929f11:6` |
| 838.2 | 1 | 1 | helper_accepted | app_crash; `b0713e2a-90a2-4bdc-a284-15dd50929f11:18` |
| 1064.6 | 1 | 1 | fault_boundary | on_qa_feedback; `b0713e2a-90a2-4bdc-a284-15dd50929f11:22` |
| 1064.7 | 1 | 2 | router_selection | app_crash; `b0713e2a-90a2-4bdc-a284-15dd50929f11:24` |
| 1462.3 | 1 | 2 | helper_accepted | app_crash; `b0713e2a-90a2-4bdc-a284-15dd50929f11:37` |
| 1659.0 | 1 | 3 | router_selection | incorrect_invoice; `b0713e2a-90a2-4bdc-a284-15dd50929f11:42` |
| 2134.6 | 1 | 3 | helper_accepted | incorrect_invoice; `b0713e2a-90a2-4bdc-a284-15dd50929f11:51` |
| 2135.4 | 1 | 3 | attempt_finished | completed; `b0713e2a-90a2-4bdc-a284-15dd50929f11:54` |

## 05_BASE-0004-QA_CORRUPTION__full_restart

| ms | Attempt | Iteration | Event | Evidence |
|---:|---:|---:|---|---|
| 265.6 | 1 | 1 | router_selection | app_crash; `453e5522-440e-49c5-b787-b95e210f31e7:6` |
| 800.7 | 1 | 1 | helper_accepted | app_crash; `453e5522-440e-49c5-b787-b95e210f31e7:18` |
| 988.0 | 1 | 1 | fault_boundary | on_qa_feedback; `453e5522-440e-49c5-b787-b95e210f31e7:22` |
| 988.2 | 1 | 2 | router_selection | app_crash; `453e5522-440e-49c5-b787-b95e210f31e7:24` |
| 1422.6 | 1 | 2 | helper_accepted | app_crash; `453e5522-440e-49c5-b787-b95e210f31e7:37` |
| 1636.7 | 1 | 3 | router_selection | incorrect_invoice; `453e5522-440e-49c5-b787-b95e210f31e7:42` |
| 1973.8 | 1 | 3 | helper_accepted | incorrect_invoice; `453e5522-440e-49c5-b787-b95e210f31e7:51` |
| 1976.5 | 1 | 3 | attempt_finished | completed; `453e5522-440e-49c5-b787-b95e210f31e7:64` |

## 06_BASE-0004-QA_CORRUPTION__always_verify

| ms | Attempt | Iteration | Event | Evidence |
|---:|---:|---:|---|---|
| 244.3 | 1 | 1 | router_selection | app_crash; `e17fef72-cabf-456e-9b2f-4dd7516196c6:6` |
| 672.7 | 1 | 1 | helper_accepted | app_crash; `e17fef72-cabf-456e-9b2f-4dd7516196c6:23` |
| 893.2 | 1 | 1 | fault_boundary | on_qa_feedback; `e17fef72-cabf-456e-9b2f-4dd7516196c6:27` |
| 893.8 | 1 | 1 | verification_decision | qa_ledger_mismatch; `e17fef72-cabf-456e-9b2f-4dd7516196c6:31` |
| 894.2 | 1 | 1 | stage_retry | qa; `e17fef72-cabf-456e-9b2f-4dd7516196c6:35` |
| 1264.2 | 1 | 2 | router_selection | incorrect_invoice; `e17fef72-cabf-456e-9b2f-4dd7516196c6:44` |
| 1572.1 | 1 | 2 | helper_accepted | incorrect_invoice; `e17fef72-cabf-456e-9b2f-4dd7516196c6:58` |
| 1573.1 | 1 | 2 | attempt_finished | completed; `e17fef72-cabf-456e-9b2f-4dd7516196c6:64` |

## 07_BASE-0004-HELPER_CORRUPTION__unprotected

| ms | Attempt | Iteration | Event | Evidence |
|---:|---:|---:|---|---|
| 395.5 | 1 | 1 | router_selection | app_crash; `3e0b47c1-90cd-43f6-adfd-ce2889708156:6` |
| 912.2 | 1 | 1 | helper_accepted | app_crash; `3e0b47c1-90cd-43f6-adfd-ce2889708156:18` |
| 1118.2 | 1 | 2 | router_selection | incorrect_invoice; `3e0b47c1-90cd-43f6-adfd-ce2889708156:24` |
| 1122.4 | 1 | 2 | fault_boundary | on_helper_output; `3e0b47c1-90cd-43f6-adfd-ce2889708156:32` |
| 1729.2 | 1 | 2 | helper_accepted | incorrect_invoice; `3e0b47c1-90cd-43f6-adfd-ce2889708156:36` |
| 1729.7 | 1 | 2 | attempt_finished | completed; `3e0b47c1-90cd-43f6-adfd-ce2889708156:39` |

## 08_BASE-0004-HELPER_CORRUPTION__full_restart

| ms | Attempt | Iteration | Event | Evidence |
|---:|---:|---:|---|---|
| 219.7 | 1 | 1 | router_selection | app_crash; `05f0f137-7a80-47df-a05d-657e86e48485:6` |
| 807.3 | 1 | 1 | helper_accepted | app_crash; `05f0f137-7a80-47df-a05d-657e86e48485:18` |
| 1014.5 | 1 | 2 | router_selection | incorrect_invoice; `05f0f137-7a80-47df-a05d-657e86e48485:24` |
| 1016.1 | 1 | 2 | fault_boundary | on_helper_output; `05f0f137-7a80-47df-a05d-657e86e48485:32` |
| 1886.1 | 1 | 2 | helper_accepted | incorrect_invoice; `05f0f137-7a80-47df-a05d-657e86e48485:36` |
| 1889.1 | 1 | 2 | verification_decision | record_unavailable_or_mismatch; `05f0f137-7a80-47df-a05d-657e86e48485:48` |
| 1889.5 | 1 | 2 | attempt_finished | failed; `05f0f137-7a80-47df-a05d-657e86e48485:51` |
| 1889.6 | 1 | 2 | restart_triggered | final_record_mismatch; `05f0f137-7a80-47df-a05d-657e86e48485:52` |
| 2089.6 | 2 | 1 | router_selection | app_crash; `05f0f137-7a80-47df-a05d-657e86e48485:67` |
| 2555.8 | 2 | 1 | helper_accepted | app_crash; `05f0f137-7a80-47df-a05d-657e86e48485:76` |
| 2804.9 | 2 | 2 | router_selection | incorrect_invoice; `05f0f137-7a80-47df-a05d-657e86e48485:81` |
| 3115.5 | 2 | 2 | helper_accepted | incorrect_invoice; `05f0f137-7a80-47df-a05d-657e86e48485:90` |
| 3117.6 | 2 | 2 | attempt_finished | completed; `05f0f137-7a80-47df-a05d-657e86e48485:103` |

## 09_BASE-0004-HELPER_CORRUPTION__always_verify

| ms | Attempt | Iteration | Event | Evidence |
|---:|---:|---:|---|---|
| 243.7 | 1 | 1 | router_selection | app_crash; `e6ae8e0d-fabc-4d6b-ae47-f29d03f4a7c1:6` |
| 708.4 | 1 | 1 | helper_accepted | app_crash; `e6ae8e0d-fabc-4d6b-ae47-f29d03f4a7c1:23` |
| 1043.0 | 1 | 2 | router_selection | incorrect_invoice; `e6ae8e0d-fabc-4d6b-ae47-f29d03f4a7c1:32` |
| 1044.6 | 1 | 2 | fault_boundary | on_helper_output; `e6ae8e0d-fabc-4d6b-ae47-f29d03f4a7c1:40` |
| 1047.6 | 1 | 2 | verification_decision | record_unavailable_or_mismatch; `e6ae8e0d-fabc-4d6b-ae47-f29d03f4a7c1:46` |
| 1047.8 | 1 | 2 | stage_retry | incorrect_invoice; `e6ae8e0d-fabc-4d6b-ae47-f29d03f4a7c1:51` |
| 1374.6 | 1 | 2 | helper_accepted | incorrect_invoice; `e6ae8e0d-fabc-4d6b-ae47-f29d03f4a7c1:65` |
| 1375.5 | 1 | 2 | attempt_finished | completed; `e6ae8e0d-fabc-4d6b-ae47-f29d03f4a7c1:72` |

## 10_BASE-0004-TIMEOUT__unprotected

| ms | Attempt | Iteration | Event | Evidence |
|---:|---:|---:|---|---|
| 209.5 | 1 | 1 | router_selection | app_crash; `cdcff45f-9482-4bf1-b404-256ef17a4063:6` |
| 210.8 | 1 | 1 | fault_boundary | on_tool_call; `cdcff45f-9482-4bf1-b404-256ef17a4063:13` |
| 211.2 | 1 | 1 | helper_unavailable | app_crash; `cdcff45f-9482-4bf1-b404-256ef17a4063:15` |
| 784.5 | 1 | 2 | router_selection | app_crash; `cdcff45f-9482-4bf1-b404-256ef17a4063:20` |
| 1192.1 | 1 | 2 | helper_accepted | app_crash; `cdcff45f-9482-4bf1-b404-256ef17a4063:29` |
| 1425.1 | 1 | 3 | router_selection | incorrect_invoice; `cdcff45f-9482-4bf1-b404-256ef17a4063:34` |
| 1764.2 | 1 | 3 | helper_accepted | incorrect_invoice; `cdcff45f-9482-4bf1-b404-256ef17a4063:43` |
| 1764.8 | 1 | 3 | attempt_finished | completed; `cdcff45f-9482-4bf1-b404-256ef17a4063:46` |

## 11_BASE-0004-TIMEOUT__full_restart

| ms | Attempt | Iteration | Event | Evidence |
|---:|---:|---:|---|---|
| 236.3 | 1 | 1 | router_selection | app_crash; `9f7d7900-e6a3-4b2a-9b94-c4a37ac6e741:6` |
| 238.1 | 1 | 1 | fault_boundary | on_tool_call; `9f7d7900-e6a3-4b2a-9b94-c4a37ac6e741:13` |
| 238.4 | 1 | 1 | attempt_finished | failed; `9f7d7900-e6a3-4b2a-9b94-c4a37ac6e741:15` |
| 238.5 | 1 | 1 | restart_triggered | helper_timeout; `9f7d7900-e6a3-4b2a-9b94-c4a37ac6e741:16` |
| 402.9 | 2 | 1 | router_selection | app_crash; `9f7d7900-e6a3-4b2a-9b94-c4a37ac6e741:26` |
| 948.8 | 2 | 1 | helper_accepted | app_crash; `9f7d7900-e6a3-4b2a-9b94-c4a37ac6e741:35` |
| 1212.5 | 2 | 2 | router_selection | incorrect_invoice; `9f7d7900-e6a3-4b2a-9b94-c4a37ac6e741:40` |
| 1561.8 | 2 | 2 | helper_accepted | incorrect_invoice; `9f7d7900-e6a3-4b2a-9b94-c4a37ac6e741:49` |
| 1564.1 | 2 | 2 | attempt_finished | completed; `9f7d7900-e6a3-4b2a-9b94-c4a37ac6e741:62` |

## 12_BASE-0004-TIMEOUT__always_verify

| ms | Attempt | Iteration | Event | Evidence |
|---:|---:|---:|---|---|
| 216.8 | 1 | 1 | router_selection | app_crash; `415379c9-46a1-4522-a6bc-698ff24b21ab:6` |
| 218.6 | 1 | 1 | fault_boundary | on_tool_call; `415379c9-46a1-4522-a6bc-698ff24b21ab:13` |
| 219.8 | 1 | 1 | verification_decision | record_unavailable_or_mismatch; `415379c9-46a1-4522-a6bc-698ff24b21ab:19` |
| 220.1 | 1 | 1 | stage_retry | app_crash; `415379c9-46a1-4522-a6bc-698ff24b21ab:24` |
| 819.8 | 1 | 1 | helper_accepted | app_crash; `415379c9-46a1-4522-a6bc-698ff24b21ab:38` |
| 1084.9 | 1 | 2 | router_selection | incorrect_invoice; `415379c9-46a1-4522-a6bc-698ff24b21ab:47` |
| 1425.0 | 1 | 2 | helper_accepted | incorrect_invoice; `415379c9-46a1-4522-a6bc-698ff24b21ab:61` |
| 1427.5 | 1 | 2 | attempt_finished | completed; `415379c9-46a1-4522-a6bc-698ff24b21ab:67` |
