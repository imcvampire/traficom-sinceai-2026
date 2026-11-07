# /risk CSV export planned

Planned a **Download CSV** button for `/risk` in `plans/261107-1402-risk-csv-export/` (fast mode, two phases, about 2h).

The CSV is built in the browser from the notices the page has already loaded. It uses the table's filtered and
sorted ids (`visibleIds`, which already feeds the chat), so the file matches what the user sees across all pages,
with no backend change. A server-side endpoint was left out: it would duplicate the table's filter logic for no
current consumer.

Points worth knowing for the implementation: guard against CSV formula injection on text cells only, so negative dB
values stay numeric; write a UTF-8 BOM so Excel reads non-ASCII names correctly; include no score column. The draft
letter's `saveFile` revokes its object URL synchronously, which can cancel downloads in some browsers. It moves to
`lib/download.ts` with a deferred revoke.

## Shipped (same day)

Implemented as planned. A headless-browser click on IFIC 3083 with `outcome=exceeds&sort=days_left.asc` exported 59
rows (more than two table pages), all `exceeds`, with `days_left` ascending and nulls last, matching the table. One
gotcha while verifying: `Blob.text()` drops a leading BOM when it decodes, so it cannot be used to check that the BOM
is there; check the raw bytes instead (EF BB BF, confirmed via Bun).
