## 새 실험

```powershell
python Code/mujin_improved.py
```

## 재개

```powershell
python Code/mujin_improved.py --resume "결과폴더경로"
```

## 정확도 그래프만 생성 — API 호출 없음

```powershell
python Code/mujin_improved.py --analyze "결과폴더경로"
```

## 음절 길이 그래프

```powershell
python Code/analyze_length.py "결과폴더경로" --window 20
