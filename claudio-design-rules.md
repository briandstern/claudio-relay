# Claudio — Daily Outfit Brief Design & Image Quality Rules

## Overall Problem to Fix
The current output looks like it was made by an AI. It needs to look like it was made by a real human stylist with a design background. Two main issues: text is too small to read on a phone, and the images look obviously AI-generated.

## Image Size & Resolution
- Output should be 1080x1920 (standard phone screen, 9:16 ratio)
- This is meant to be glanced at on a phone while getting dressed — everything must be readable at arm's length
- If the image can't be read without zooming in, it's too small

## Typography Rules
- **Minimum font size: 28px** for any body text on the card
- **Item names: 32-36px bold**
- **Item details (color, brand): 28-30px regular**
- **Section headers (FLAT LAY GRID, FULL LOOK): 24px uppercase tracking**
- **Header bar text (DAILY OUTFIT BRIEF): 40-48px bold**
- **Stylist note: 30-34px italic**
- **Client name / date: 32-36px**
- No text should ever be below 24px — if it doesn't fit, reduce content, don't reduce font size
- High contrast: dark text on light backgrounds, light text on dark backgrounds
- Limit to 2 font families max (one sans-serif for headers/labels, one serif for the stylist note)

## Image Quality — CRITICAL
The product images and the full look visualization are the #1 thing that makes this look real or fake. Follow these rules:

### Flat Lay Grid (Left Side) — Product Images
- **Use real product photography, not AI-generated images**
- Source images from retailer websites, brand lookbooks, or stock photo sites
- Product images should have clean white or light grey backgrounds — like what you'd see on Mr Porter, Nordstrom, or SSENSE
- No AI artifacts: no weird stitching, no melting fabric, no impossible buttons, no uncanny textures
- Each image should look like a standalone product photo you'd find in an online store
- If you must use AI-generated images, use prompts that specify: "product photography, white background, studio lighting, e-commerce style photo, no model, flat lay, 8k, photorealistic"
- Avoid: floating garments, impossible folds, text on clothing, brand logos that don't exist

### Full Look Visualization (Right Side)
- This should look like a **street style photograph** or **editorial lookbook shot** — NOT an AI portrait
- The style reference is: The Sartorialist, GQ street style, Mr Porter editorial shoots
- If AI-generated, use prompts that specify: "candid street style photo, natural lighting, urban setting, shot on 85mm lens, shallow depth of field, editorial fashion photography, NOT posed, NOT studio"
- The model should look natural — real skin texture, natural hair, realistic proportions
- Setting should be urban/city (NYC streets, cobblestone, building entrances) with natural light
- Camera angle: slightly below eye level or straight on, never from above
- **Do NOT include the model's face looking directly at camera** — looking away, in motion, or cropped at chin is more editorial and avoids the uncanny valley
- Avoid: plastic-looking skin, impossible hand positions, weird fingers, symmetrical poses, studio backgrounds pretending to be outdoor

### Color Palette Bar (Bottom)
- Keep it but make the swatches larger (at least 60x60px each)
- Color name text: 28px minimum

## Layout Refinements
- **More white space** — the current version is too cramped. Let elements breathe.
- **Grid items should be larger** — each product image cell should be at least 400x400px within the layout
- **Reduce the number of items if needed** — 4-5 items max in the flat lay grid. Quality over quantity. Don't include a coat/overcoat unless it's a key style piece — I know I need a coat when it's cold.
- **Stylist note should be prominent** — this is the personal touch. It should be easy to read, not buried at the bottom in tiny text.
- **Weather bar in the header** is good — keep it concise (temp, conditions, one emoji)

## What "Real Stylist" Output Looks Like
Think about what a personal stylist charges $500/month for. They send you:
- A clean, well-designed card that could be an Instagram post
- Real product photos that look like they came from a shopping site
- A styled photo that looks like it came from a fashion blog or magazine
- A short, confident note that feels personal — cot a paragraph, just 1-2 sentences
- It feels curated and human, not generated and algorithmic

## Test: Before Finalizing Any Output, Ask These Questions
1. Could I post this on Instagram and people would think a real stylist made it? If no, fix it.
2. Can I read every word on my phone without zooming? If no, make text bigger.
3. Do the product images look like they came from a real store? If no, re-source them.
4. Does the full look photo look like a real person photographed on a real street? If no, re-generate with better prompts.
5. Does anything look "off" in an uncanny valley way? If yes, fix or remove it.
