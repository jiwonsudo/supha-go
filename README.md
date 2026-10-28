# SuphaGo

수박게임을 스스로 학습하는 AI입니다. 이름은 Suika(수박) + AlphaGo에서 왔습니다.

웹 수박게임(playsuikagame.com)과 같은 규칙과 물리로 돌아가는 헤드리스 엔진을 만들고, 그 위에서 사람이 만든 채점 공식으로 두는 탐색 AI부터 학습된 신경망을 붙인 AI까지 단계별로 비교합니다. 만든 AI는 실제 사이트에서도 플레이할 수 있습니다.

## 진행 상황

| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | 원본과 같은 헤드리스 엔진 | 완료 |
| 2 | 베이스라인 (랜덤, 타입매칭, 몬테카를로) | 완료 |
| 3 | 가치망 (판을 보고 앞으로의 점수 예측) | 진행 중 |
| 4 | MCTS + 정책망 + 자가학습 | 예정 |
| 5 | 비교 정리, 웹 데모 | 예정 |

## 결과 (엔진, 60Hz, 30판)

| 에이전트 | 중앙값 | 25% | 75% |
|---|---|---|---|
| 랜덤 | 1219 | 1090 | 1347 |
| 타입매칭 (같은 과일 위에 떨어뜨리기) | 1951 | 1618 | 2301 |
| 몬테카를로 1수 (후보 50곳을 굴려보고 고르기) | 3556 | 3024 | 4012 |
| 몬테카를로 2수 (다음 과일까지 굴려보기) | 4080 | 3724 | 4282 |

실제 사이트에서 몬테카를로 1수가 4107점(시드 0, 60Hz)을 냈습니다. 자세한 실험 기록은 [docs/experiments.md](docs/experiments.md)에 있습니다.

## 문서

| 문서 | 내용 |
|---|---|
| [docs/architecture.md](docs/architecture.md) | 전체 구조, 각 파일의 역할, 데이터 흐름 |
| [docs/engine.md](docs/engine.md) | 원본 분석, 물리값, 게임 규칙, 검증 방법 |
| [docs/ai.md](docs/ai.md) | 에이전트, 판 인코딩, 신경망, 학습, 가치망 에이전트 |
| [docs/live-play.md](docs/live-play.md) | 실제 사이트에서 플레이하는 방식과 찾은 버그들 |
| [docs/experiments.md](docs/experiments.md) | 실험 기록과 결과, 분석 |
| [docs/running.md](docs/running.md) | 설치와 실행 명령 모음 (맥, 클라우드) |

## 빠른 시작

```bash
cd engine && npm ci && cd ..
cd python && pip install -r requirements.txt
python3 -m suphago.bench --agent mc --games 10 --workers 8
```

리플레이 뷰어: 레포 루트에서 `python3 -m http.server 8000` 실행 후 `http://localhost:8000/viewer/`

## 구조

```
engine/          Node.js + Matter.js 시뮬레이터 (게임 엔진, 워커, 검증 테스트)
python/suphago/  에이전트, 신경망, 학습, 벤치마크, 실제 사이트 플레이
viewer/          리플레이 뷰어
cloud/           Google Cloud에서 벤치마크·수집 돌리는 스크립트
replays/         샘플 리플레이
results/         벤치마크와 실제 사이트 플레이 기록
docs/            문서
```
