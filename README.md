# SuphaGo

수박게임을 스스로 학습하는 AI 프로젝트입니다. playsuikagame.com과 같은 규칙·물리로 돌아가는 헤드리스 엔진 위에서 베이스라인 → 가치망 → MCTS + 자가학습 순서로 올라갑니다.

## 구조

```
engine/          Node + Matter.js 시뮬레이터
  src/suika.js   게임 엔진 (reset, turn, clone)
  src/server.js  JSON 줄 단위 워커 (Python이 서브프로세스로 실행)
  test/          원본 비교, clone 결정성, 상태 해시 테스트
python/suphago/
  bridge.py      Node 워커와 통신
  agents.py      랜덤, 타입매칭, 몬테카를로 베이스라인
  bench.py       병렬 벤치마크 (중앙값, 25/75%)
```

## 실행

```bash
cd engine && npm install && cd ..
cd python
python3 -m suphago.bench --agent random --games 30 --workers 8
python3 -m suphago.bench --agent typematch --games 30 --workers 8
python3 -m suphago.bench --agent mc --mode combined --plies 2 --games 30 --workers 10 --out mc.jsonl
```

워커 하나가 Node 프로세스 하나라서 `--workers`는 CPU 코어 수에 맞추면 됩니다.

## 엔진

- 물리: Phaser 3.70.0에 들어 있는 Matter.js 0.19.0 소스를 그대로 사용
- 규칙: 원본 페이지에서 확인한 동작을 직접 구현 (원본 게임 코드는 포함하지 않음)

| 항목 | 값 |
|---|---|
| 중력 | y 1.5, scale 0.001 |
| 솔버 | position 6, velocity 4, restingThresh 4, restingThreshTangent 6 |
| 과일 | 원형(26각형), friction 1, frictionStatic 0.5, frictionAir 0.01, restitution 0, 0.75배 스케일 |
| 통 | 캔버스 654×724, 벽 x 55~599, 바닥 y 708 |
| 생성 | 첫 과일 체리 고정, 이후 작은 5종 균등 랜덤, 다음 과일 공개 |
| 낙하 | y 80, 다음 낙하까지 600ms (60Hz 36프레임, 120Hz 72프레임) |
| 점수 | 1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 66 |
| 게임오버 | 다른 과일끼리 충돌할 때 한쪽의 (y - centerOffset.y/2) < 70 |

```js
const { SuikaGame } = require('./engine/src/suika');
const g = new SuikaGame({ seed: 1, displayHz: 60 });
g.turn(300);          // 현재 과일을 x=300에 떨어뜨리고 다음 낙하 가능 시점까지 진행
const b = g.clone();  // 탐색용 분기 (같은 수를 두면 같은 결과)
```

### 원본과의 일치 정도

- 원본 페이지에서 녹화한 24수 시나리오와 비교하면 점수·과일 구성은 끝까지 같고, 좌표는 약 9수까지 소수점 12자리까지 같습니다.
- 그 뒤 좌표가 벌어지는 건 브라우저와 Node의 `Math.sin`/`Math.cos` 결과가 마지막 자리에서 달라서입니다. 원본도 브라우저마다 같은 이유로 조금씩 다르게 돌아갑니다.

### 속도

한 프레임 비용의 약 70%가 충돌 판정(SAT)이고, 판정 호출의 약 90%가 실제 접촉이라 결과를 바꾸지 않는 최적화 여지는 거의 없습니다. 속도는 워커 병렬로 확보합니다.

## 검증

- `node engine/test/compare_ref.js`: 원본 녹화 시나리오(120Hz)와 비교
- `node engine/test/clone_and_speed.js`: clone 결정성, 속도
- `node engine/test/golden.js`: 상태 해시 (엔진 수정 후 값이 바뀌면 결과가 바뀐 것)
