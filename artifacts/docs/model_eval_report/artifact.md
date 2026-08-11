# Template execution contract

## Reference

- Source: `C:\Users\Playdata\Downloads\모델링 및 평가_테스트 계획 및 결과 보고서_2팀.docx`
- SHA-256: `1e461f93b43c76f9a0bbe573b985133a839ab10295a1d3bae55af50a31f5d0f2`
- Baseline: 4 rendered pages, 1 section, 39 body paragraphs, 5 tables.
- Evidence: `template-evidence.json`, `template-style-evidence.json`, `reference_render/reference.pdf`, and `reference_render/page-1.png` through `page-4.png`.
- Render method: the canonical LibreOffice renderer was attempted and failed because `soffice` is not installed. Microsoft Word 16 read-only PDF export plus bundled `pypdfium2` rasterization is the visual authority for this task.

## Page system

- A4 portrait, 8.2681 x 11.6931 inches.
- One-inch margins on all sides; header/footer distance 0.4917 inches.
- One continuous section; no columns, first-page variant, headers, footers, page fields, or section breaks.
- Baseline page patterns: page 1 title/metadata/overview; page 2 environment plus functional TC table; page 3 continuation tables; page 4 history/conclusion.
- The completed report may add pages as table rows expand, but page geometry and margins must remain unchanged.

## Typography and components

- Opening title block: centered Normal paragraphs, 15 pt bold; first line has 10 pt before/3 pt after, second line 16 pt after.
- Heading 1: 14 pt, bold, dark navy `1F3864`, 16 pt before/8 pt after.
- Heading 2: 12 pt, bold, blue `2E5395`, 13 pt before/6.5 pt after.
- Heading 3: 10.5 pt, bold, dark gray `404040`, 10 pt before/5 pt after.
- Body/list content uses the source document's Normal and List Paragraph styles and existing numbering definitions. Korean glyph rendering from Word is the fidelity reference.
- Metadata table: 9026 DXA grid, columns 2000/7026.
- Functional TC table: 9026 DXA, columns 1050/1500/2650/2226/800/800, repeated blue header row.
- Performance TC table: 9026 DXA, columns 1050/1750/2650/1500/1150/926.
- Stability TC table: 9026 DXA, columns 1050/1900/3000/2200/876.
- History table: 9026 DXA, columns 2400/900/1400/1300/3026.
- All source tables use `Normal Table`, light blue headers, thin gray borders, expandable rows, and centered short-value columns. Existing grid/width XML is preserved. The added AI quality table clones the performance table geometry and header treatment.

## Content flow and slot map

- Metadata table: fill submission date, GitHub path, and team name; preserve labels and table styling.
- Sections 1-2: replace blank bullet values with the actual test period, target, and four test objectives.
- Section 3.1: record the local Windows test machine; mark unused RunPod/AWS slots accurately.
- Section 3.2: record measured runtime/library versions and the active MySQL/Chroma/OpenAI architecture.
- Insert section 3.3 before existing 3.4 using cloned Heading 2 and list paragraph patterns; summarize the implemented product scope and the verification boundary.
- Section 3.4: replace the blank bullet with actual test tools and commands.
- Section 4.1: fill all 12 existing functional TC rows.
- Section 4.2: replace the blank Heading 3 slot with a short evaluation note and insert one cloned six-column, five-row AI quality table.
- Section 4.3: fill all four existing performance TC rows.
- Section 4.4: fill all five existing stability/error TC rows.
- Section 5: fill six history rows from selected Git commits and the current merge/test milestone.
- Section 6: replace the blank paragraph with a concise outcome, limitations, and recommended follow-up actions.

## Package preservation

- Preserve styles, numbering, theme, settings, relationships, core/app properties, and all table XML not deliberately edited.
- No images, drawings, comments, tracked changes, content controls, footnotes, endnotes, bookmarks, hyperlinks, or fields exist in the reference.
- The reference has 18 package parts, inventoried by path/size/SHA-256 in `template-evidence.json`; no opaque `customXml` or media parts require preservation.
- Permitted changes are document body text, added body paragraphs, the added AI quality table, and pagination resulting from content growth.

## Fidelity gates

- The source SHA-256 must remain unchanged.
- Section count, A4 geometry, margins, heading color ladder, list indentation, table fills/borders, and table grid widths must match the source.
- All table rows must expand naturally; no fixed heights, clipping, overlap, orphaned header rows, or unreadable wrapped cells.
- Every final page must be inspected at 100% after Word PDF export and PNG rasterization.
- Final content must contain no placeholders, encoding corruption, conflict markers, secret values, internal tool tokens, or unsupported claims.
