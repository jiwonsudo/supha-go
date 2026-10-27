# SuphaGo

수박게임 AI 프로젝트. 1단계는 playsuikagame.com과 같은 규칙·물리로 돌아가는 헤드리스 엔진입니다.

## 엔진 (`engine/`)

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

## 검증

- `node engine/test/compare_ref.js`: 원본 페이지에서 녹화한 24수 시나리오(120Hz)와 비교
- `node engine/test/clone_and_speed.js`: clone 결정성, 속도 측정
