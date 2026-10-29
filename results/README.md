# 결과 파일

판별 기록은 한 줄에 한 판입니다(`seed`, `score`, `turns`, `agent` 등). 60Hz, 후보 50곳(combined) 기준입니다. 실험 번호는 [docs/experiments.md](../docs/experiments.md)를 따릅니다.

## 벤치마크

| 파일 | 에이전트 | 시드 | 판 | 실험 |
|---|---|---|---|---|
| `baselines_2026-10-27.jsonl` | 랜덤, 타입매칭 (+ 동작 확인용 MC 2판) | 0~29 | 30씩 | 1 |
| `mc1.jsonl` | MC 1수 | 0~29 | 30 | 1 |
| `mc2.jsonl` | MC 2수 | 0~29 | 30 | 1 |
| `mc2_s30_99.jsonl` | MC 2수 | 30~99 | 70 | 12 |
| `mcv_a0_r1.jsonl` | mcv 1수 + h30_all, 게임오버 벌점만 | 0~29 | 30 | 6 |
| `mcv_a1_r1.jsonl` | mcv 1수 + h30_all | 0~29 | 30 | 6 |
| `mc1_pw.jsonl`, `mc2_pw.jsonl` | MC 1수·2수 + 큰 과일 보너스 | 0~29 | 30 | 8 |
| `mc2_pw5.jsonl` | MC 2수 + 보너스 5배 | 0~29 | 30 | 8 |
| `mcv1_v3.jsonl` | mcv 1수 + v3 | 0~29 | 30 | 10 |
| `mcv1_v3_s30_99.jsonl` | mcv 1수 + v3 | 30~99 | 70 | 12 |
| `mcv2_h30all.jsonl` | mcv 2수 + h30_all | 0~29 | 30 | 10 |
| `mcv2_v3.jsonl` | mcv 2수 + v3 | 0~29 | 30 | 10 |
| `mcv2_v4.jsonl` | mcv 2수 + v4 | 0~29 | 30 | 10 |
| `mcv2_v4_s30_99.jsonl` | mcv 2수 + v4 (시간 문제로 일부만) | 30~97 중 58개 | 58 | 12 |
| `ps_v3.jsonl`, `ps_v4.jsonl`, `ps.jsonl` | 정책망 탐색 + v3, + v4, 가치망 없음 | 0~29 | 30 | 11 |

## 기보 점수

| 파일 | 기보 | 판 | 실험 |
|---|---|---|---|
| `collect_mc2_mac.jsonl` | MC 2수 (맥, 시드 100110~) | 110 | 5 |
| `collect_sp1.jsonl` | 자가학습 1회차: mcv 1수 + v3 (시드 200000~) | 200 | 12 |

## 학습 로그

| 파일 | 모델 | 실험 |
|---|---|---|
| `train_value_mc1.log` | value_mc1 | 3 |
| `train_value_h30_all.log` | value_h30_all | 5 |
| `train_value_v3.log` | value_v3 | 10 |
| `train_value_v4.log` | value_v4 (8에폭에서 중단) | 10 |
| `train_policy_v1.log` | policy_v1 | 11 |

## 실제 사이트

`live/`에 MC 1수 시드 0의 v1~v3 기록이 있습니다(실험 2). 설명은 [live/README.md](live/README.md)에 있습니다.
