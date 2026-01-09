# Equipment Scanner

Upload equipment screenshots to auto-extract potential stats using OCR.

## How to Use

1. Navigate to **Equipment Scanner** in the sidebar
2. Upload a screenshot of your equipment's **Potential Options** panel
3. Select which equipment slot this is (hat, top, weapon, etc.)
4. Click **Scan Screenshot** to run OCR
5. Review and correct any misread stats using the dropdowns
6. Click **Save to Equipment** to update your data

## Screenshot Tips

For best OCR results:
- Include the full **Potential Options** panel (right side of equipment screen)
- Make sure the tier badge (Legendary, Mystic, etc.) is visible
- Include the pity counter (e.g., 321/714)
- Avoid cropping too tightly around the text

## What Gets Extracted

| Field | Example |
|-------|---------|
| Stars | ★18 |
| Regular Potential Tier | Legendary, Mystic |
| Regular Potential Pity | 321/714 |
| Regular Potential Lines | DEX 12%, Critical Rate 9% |
| Bonus Potential Tier | Unique, Legendary |
| Bonus Potential Pity | 156/417 |
| Bonus Potential Lines | DEX 6%, Damage 3% |

## Supported Stats

The scanner recognizes these stat types:

**Main Stats (%):**
- DEX, STR, INT, LUK

**Main Stats (flat):**
- DEX, STR, INT, LUK (auto-detected based on value magnitude)

**Combat Stats:**
- Damage %, Critical Rate %, Critical Damage %
- Final Damage %, Defense Penetration %
- Min Damage %, Max Damage %

**Special Stats:**
- All Skills, Attack Speed %
- Buff Duration %, Skill Cooldown
- BA Targets +, Stat per Level

## Technical Details

### OCR Engine
Uses [EasyOCR](https://github.com/JaidedAI/EasyOCR) with English language model.

First-time setup downloads ~100MB model file (one-time only).

### Parsing Strategy
1. **Section Detection**: Identifies Regular vs Bonus potential sections by finding tier names (Legendary, Mystic, etc.)
2. **Spatial Filtering**: Uses x/y coordinates to focus on the right panel (potential options) and ignore left panel (equipment stats)
3. **Fuzzy Matching**: Matches OCR text to known stat vocabulary using similarity scoring
4. **Value Pairing**: Combines separate stat names ("DEX") and values ("12%") that OCR returns as individual items

### Confidence Levels
- **High (80%+)**: Green - likely correct
- **Medium (50-79%)**: Yellow - verify against screenshot
- **Low (<50%)**: Red - probably needs manual correction

## Troubleshooting

### Wrong stat detected?
Use the dropdown to select the correct stat from the list.

### Value incorrect?
Manually type the correct value in the number input.

### Low confidence on all lines?
Check the "Raw OCR Text" expander to see what was extracted. The OCR might have had trouble with the image quality.

### Debug Info
Expand "Debug Info" to see:
- X/Y coordinate thresholds used for filtering
- Where section boundaries were detected
- Which lines were extracted and their confidence scores

## Requirements

```
easyocr>=1.7.0
Pillow>=9.0.0
```

Install with:
```bash
pip install easyocr Pillow
```
