# Output contract

Create the final files beside `SCRAPE-SUMMARY.json`. After the manifest is complete, use the bundled renderer to create `visual-dashboard.html`.

## VISUAL-BRAND-DNA.md

Use this structure:

1. Brand overview
   - Brand name
   - Website
   - Generated date
   - Overall confidence
   - Short visual personality summary
2. Core palette
   - Table columns: role, semantic name, value, usage, evidence, confidence
   - Prefer six-digit hex values when an equivalent hex value is supported
3. Typography
   - Table columns: role, family, size, weight, line height, usage, evidence, confidence
   - Do not claim that a font is licensed or available outside the source site
4. Components
   - Buttons, navigation, cards, inputs, badges, and repeated sections only when supported
5. Layout and spacing
6. Imagery direction
7. Source pages
8. Caveats

Keep factual evidence separate from interpretation. Quote only short interface labels when they materially support a conclusion.

## brand-manifest.json

Write valid JSON with this top-level shape:

```json
{
  "version": 1,
  "brandName": "Example",
  "websiteUrl": "https://example.com/",
  "generatedAt": "ISO-8601 timestamp",
  "summary": "Short source-backed summary",
  "confidence": "high",
  "personality": ["precise", "warm"],
  "colors": [
    {
      "name": "Primary action",
      "value": "#112233",
      "role": "Primary buttons and key accents",
      "evidence": "Homepage branding and repeated CTA styling",
      "confidence": "exact"
    }
  ],
  "typography": [
    {
      "name": "Display heading",
      "family": "Example Sans",
      "size": "48px",
      "weight": "700",
      "lineHeight": "1.1",
      "usage": "Primary page headings",
      "evidence": "Homepage branding and rendered H1",
      "confidence": "exact"
    }
  ],
  "components": [],
  "layoutRules": [],
  "imageryDirection": [],
  "sourcePages": [],
  "caveats": []
}
```

Allowed confidence values are `exact`, `observed`, and `inferred`. Overall confidence is `high`, `medium`, or `low`.

Each `sourcePages` item must include `label`, `url`, `description`, and the evidence file paths recorded in `SCRAPE-SUMMARY.json`.

## brand-tokens.css

Create a small portable token file:

```css
:root {
  --brand-color-primary-action: #112233;
  --brand-font-display-heading: "Example Sans", sans-serif;
  --brand-radius-button: 8px;
}
```

Rules:

- Use kebab-case custom-property names.
- Include only supported values.
- Sanitize values; never copy braces, semicolons, or HTML into a value.
- Add no remote font imports and no `@font-face` declarations.
- Omit a token when the evidence does not support a safe value.

## visual-dashboard.html

Do not hand-author this file. Run `scripts/render_dashboard.py` after `brand-manifest.json` and `SCRAPE-SUMMARY.json` exist.

The renderer creates a responsive visual gallery containing:

- Brand overview and confidence
- Color, typography, component, artifact, and source-page metrics
- Large palette swatches with copyable values
- Typography specimen cards
- Component, layout, and imagery direction galleries
- Desktop and mobile source-page captures
- Caveats and evidence notes

The dashboard must remain portable: inline CSS and JavaScript, relative screenshot paths, no font downloads, and no build step.
