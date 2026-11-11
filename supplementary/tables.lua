-- Pandoc filter: give every table relative column widths proportional to its content, so that wide tables wrap
-- inside the page in PDF output. Header text counts less than body text (headers may wrap).
local function len(cell)
  local s = pandoc.utils.stringify(cell.contents)
  return utf8.len(s) or #s
end

function Table(tbl)
  local n = #tbl.colspecs
  local w = {}
  for i = 1, n do w[i] = 4 end
  for _, row in ipairs(tbl.head.rows) do
    for i, cell in ipairs(row.cells) do w[i] = math.max(w[i], math.min(len(cell), 14)) end
  end
  for _, body in ipairs(tbl.bodies) do
    for _, row in ipairs(body.body) do
      for i, cell in ipairs(row.cells) do w[i] = math.max(w[i], math.min(len(cell), 70)) end
    end
  end
  local total = 0
  for i = 1, n do total = total + w[i] end
  for i = 1, n do tbl.colspecs[i] = {tbl.colspecs[i][1], 0.99 * w[i] / total} end
  return tbl
end
