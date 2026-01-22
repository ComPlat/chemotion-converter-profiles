# Converter Loop Documentation

---

# Backend

## Overview

The code contains two methods (functions inside a class):

1. `_has_loop(index)`  
   Checks whether a certain output table has a “loop” configuration (i.e. is meant to be repeated for multiple input tables).

2. `_check_loop_condition(index, input_table_index)`  
   Checks whether a specific input table matches the conditions of that loop and is therefore allowed to be used in it.

In simple terms:  
You have several **input tables** (`input_tables`) and several **output table configurations** (`profile_output_tables`). Some output tables are configured so that they will be created multiple times, once for each input table that fits certain rules. These two methods help answer:

- **Does this output table have a loop at all?**  
- **Does this particular input table fit the loop conditions for that output table?**

---

## Data Structures Involved

The class that contains these methods uses at least these two properties:

- `self.profile_output_tables`  
  A list of **output table configurations**.  
  Each configuration can contain, among other things:
  - `loopType` – the type of loop, e.g. `'all'`
  - `matchTables` – which tables are targeted when `loopType = 'all'`
  - `table` – detailed configuration, including:
    - `loop_header` – rules based on columns (table headers)
    - `loop_theader` – rules based on text / pattern matches
    - `loop_metadata` – rules based on metadata

- `self.input_tables`  
  A list of the actual **input tables**.  
  Each input table can contain:
  - `columns` – a list of columns (with names, etc.)
  - `metadata` – additional key–value information about the table

---

## Method: `_has_loop(self, index)`

### Purpose

Determine whether the output table at position `index` has a loop configuration, and if so, what kind of loop it is.

### Step-by-step behavior

1. **Check if the output table exists at this index**  
   - If there is no configuration at `index`, the method returns `False`.  
     Meaning: There is no output table here, so there can’t be any loop.

2. **Case 1: `loopType` is `'all'`**  
   - This usually means:  
     “This output table should be produced for all relevant input tables (or a defined group of tables).”
   - In this case, the method returns the value of `matchTables`.  
     `matchTables` describes which tables this loop applies to (for example “all” or a specific subset).

3. **Case 2: `loopType` is not `'all'`**  
   - The method checks the `table` configuration for any of these fields:
     - `loop_header`
     - `loop_metadata`
     - `loop_theader`
   - If at least one of these has a value (is not empty), the method returns `True`.  
     Meaning: Some kind of loop configuration exists (based on headers, metadata, or text patterns).
   - If all three are empty or missing, the method returns `False`.

### Result summary

- `False`:  
  There is no loop configuration for this output table.
- `True`:  
  There is some loop configuration (via header, metadata, or text pattern).
- A value / list (e.g. `matchTables`):  
  If `loopType = 'all'`, the method directly returns the configured table selection.

---

## Method: `_check_loop_condition(self, index, input_table_index)`

### Purpose

Check if a specific input table (given by `input_table_index`) fulfills all the rules defined for the loop of the output table at position `index`.

Only if **all** conditions are satisfied, the method returns `True`.  
Otherwise, it returns `False`.

### Special case: `loopType = 'all'`

If the output table’s `loopType` is `'all'`, then at the end of the method it simply returns `True`.  
Meaning: In this mode, detailed conditions are not enforced here – all targeted tables are treated as matching.

The detailed checks described next only apply when `loopType` is **not** `'all'`.

---

### Detailed Checks (when `loopType` ≠ `'all'`)

#### 1. `loop_header` – Column / header conditions

- The method reads a list of rules from `loop_header`.
- For each rule:
  - It checks that a column reference is provided (with `tableIndex` and `columnIndex`).  
    If any of this is missing or invalid, it returns `False`.
  - It checks that the referenced column actually exists in the specified input table.
  - If the rule points to a different input table than the one currently being checked (`input_table_index`):
    - It compares the column name in that other table with the column name in the current table at the same column position.
    - If the names do not match, it returns `False`.

**Plain-language interpretation:**  
All the column rules in `loop_header` must pass.  
Typically, this means that certain columns (by position) must exist and have the same names across different input tables.

---

#### 2. `loop_theader` – Text / pattern conditions

- The method reads a list of rules from `loop_theader`.
- For each rule, it uses an internal helper (`_search_regex`) to check whether a particular text or pattern is found in the current input table header.
- If the pattern is not found (i.e. no match), it returns `False`.

**Plain-language interpretation:**  
The input table must contain certain texts or patterns (for example in headers or specific rows), as defined in the configuration.

---

#### 3. `loop_metadata` – Metadata conditions

- The method reads a list of rules from `loop_metadata`.
- For each metadata rule:
  - A `value` (the metadata key) and a `table` must be provided.  
    If either is missing, it returns `False`.
  - Then there are two modes:
    1. **If `ignoreValue` is set to true:**  
       - The rule only requires that the current input table (`input_table_index`) has this metadata key at all.  
         If the key is missing, the method returns `False`.
    2. **If `ignoreValue` is not set:**  
       - The rule identifies a “reference table” by the provided table index.
       - It looks up the metadata value for the given key in that reference table.
       - It compares that value with the value under the same key in the current input table.
       - If the values differ, the method returns `False`.

**Plain-language interpretation:**  
The current input table’s metadata must either:
- contain certain keys, or
- contain keys with values that match those in another table,

depending on the configuration.

---

## Overall Summary

- `_has_loop(index)` answers:  
  “Does this output table have a loop configuration, and what kind is it?”

- `_check_loop_condition(index, input_table_index)` answers:  
  “Does this particular input table fulfill all conditions to be used in the loop for this output table?”

Typically, the system would:

1. Use `_has_loop` to see whether an output table is supposed to be repeated for multiple input tables.
2. For each input table, use `_check_loop_condition` to decide whether that table is included in the loop.

Only if `_has_loop` identifies a loop **and** `_check_loop_condition` returns `True` for a certain input table will that table be processed as part of the repeated output.

# Frontend

This part of the frontend is the visual configuration for the loop logic you saw in the backend.

It lets a user decide:

1. **Whether an output table should be repeated for multiple input tables**, and  
2. **According to which rule those input tables should be selected.**

Below is what each visible element means and how it connects to the backend behavior.

---

## 1. The “Select looping” dropdown (`loopType`)

```jsx
<Form.Select
  id="loop_select"
  aria-label="Select looping"
  value={profile.tables[index].loopType}
  onChange={(e) => this.handleChangeLoop(e.target.value, index)}
>
  <option value="all">all input tables.</option>
  <option value="header">all input tables that have the same column header.</option>
  <option value="theader">all input tables that have the same table header.</option>
  <option value="metadata">all input tables that have the same metadata.</option>
</Form.Select>
```

### What the user sees

A dropdown with these options:

- **“all input tables.”**
- **“all input tables that have the same column header.”**
- **“all input tables that have the same table header.”**
- **“all input tables that have the same metadata.”**

The user chooses one of these options for each output table.

<img width="785" height="443" alt="grafik" src="https://github.com/user-attachments/assets/02b32599-05c6-4f22-adca-d9cbb5e5cb32" />


### How this relates to the backend

The selected value is stored as `loopType` in `profile.tables[index].loopType`. In the backend, this corresponds to:

- `self.profile_output_tables[index].get('loopType')`

The options mean:

- **`all`**  
  Backend: `loopType = 'all'`  
  → The output table is generated for *all* input tables (no detailed conditions are checked in `_check_loop_condition`; it effectively always returns `True`).

- **`header`**  
  Backend: `loopType` is not `'all'`, and the frontend uses `loop_header` rules.  
  → The backend uses `loop_header` to check if input tables have matching **column headers** (column names and positions).

  <img width="1626" height="414" alt="grafik" src="https://github.com/user-attachments/assets/43d39f23-4b86-4067-8aef-ada996008947" />


- **`theader`**  
  Backend: `loopType` is not `'all'`, and the frontend uses `loop_theader`.  
  → The backend uses `loop_theader` and `_search_regex` to check for **matching table header text/patterns**.

  <img width="742" height="106" alt="grafik" src="https://github.com/user-attachments/assets/91eb1a42-f501-47da-aedb-068eb2692699" />


- **`metadata`**  
  Backend: `loopType` is not `'all'`, and the frontend uses `loop_metadata`.  
  → The backend uses `loop_metadata` to compare **metadata values** between tables.

  <img width="760" height="112" alt="grafik" src="https://github.com/user-attachments/assets/1e6145cb-9829-4845-a24f-3fd51c21a368" />

- **it is also possible to combine all settings with a logical "&"**

  <img width="754" height="184" alt="grafik" src="https://github.com/user-attachments/assets/1ab58e89-7f59-4421-9718-dae5087fc625" />



So, this dropdown directly controls **which type of loop condition** the backend will apply.

---

## 2. Column-based rules: `loop_header` (for “same column header”)

```jsx
{profile.tables[index].loopType !== "all" &&
 profile.tables[index].table['loop_header'] &&
 profile.tables[index].table['loop_header'].map((operation, op_index) => (
  <InputGroup key={op_index}>
    <InputGroup.Text>&#8627;</InputGroup.Text>
    <Button
      variant="outline-danger"
      onClick={() => this.removeOperation(index, 'loop_header', op_index)}
    >
      &times;
    </Button>
    <Select
      ...
      value={distInputColumns.flatMap(group => group.options)
        .find(col => isEqual(col.value, operation.column))}
      options={distInputColumns}
      onChange={selectedOption =>
        this.updateOperation(index, 'loop_header', op_index, 'column', selectedOption.value)
      }
    />
  </InputGroup>
))}
```

### What the user sees

Only shown when `loopType` is **not** `"all"`, and there are `loop_header` rules.

For each rule, the user sees:

- An arrow-like symbol (`↧` style via `&#8627;`) indicating “this is part of the loop configuration”.
- A red **X button** to remove this rule.
- A dropdown (React `Select`) showing all available input columns, grouped by table. The user picks one column.

The user can create or remove several such rules (each rule picks one column).

### How this relates to the backend

Each selected column is stored as one entry in:

- `profile.tables[index].table['loop_header'][op_index].column`

In the backend, `_check_loop_condition` uses:

```python
loop_header = self.profile_output_tables[index]['table'].get('loop_header', [])
for header in loop_header:
    header['column'] -> { tableIndex, columnIndex }
```

The backend then:

- Checks that this column exists in the referenced input table.
- Ensures that in the current input table being tested, the column at the same position has the **same name**, unless it is the same table.

**Effect:**  
You are telling the system:  
“Only treat input tables as belonging to the same loop if these specific columns match across the tables.”

The frontend control is exactly how you specify *which* columns must match.

---

## 3. Metadata-based rules: `loop_metadata` (for “same metadata”)

```jsx
{profile.tables[index].loopType !== "all" &&
 profile.tables[index].table['loop_metadata'] &&
 profile.tables[index].table['loop_metadata'].map((operation, op_index) => (
  <InputGroup key={op_index}>
    <InputGroup.Text>&#8627;</InputGroup.Text>
    <Button
      variant="outline-danger"
      onClick={() => this.removeOperation(index, 'loop_metadata', op_index)}
    >
      &times;
    </Button>
    <Form.Select
      size="sm"
      value={operation.metadata || ''}
      onChange={(event) => {
        this.updateOperation(
          index,
          'loop_metadata',
          op_index,
          'metadata',
          `${event.target.value}:${tableMetadataOptions[event.target.value].key}:${tableMetadataOptions[event.target.value].tableIndex}`
        );
      }}
    >
      {tableMetadataOptions.map((option, optionIndex) => (
        <option key={optionIndex} value={optionIndex}>{option.label}</option>
      ))}
    </Form.Select>
    <OverlayTrigger
      placement="bottom-end"
      overlay={<Tooltip>Ignore Value</Tooltip>}
    >
      <div className="input-group-text" style={{cursor: 'pointer'}}>
        <input
          type="checkbox"
          checked={profile.tables[index].table.loop_metadata[op_index].ignoreValue || false}
          onChange={() => this.toggleMatchTables(index, op_index)}
        />
      </div>
    </OverlayTrigger>
  </InputGroup>
))}
```

### What the user sees

Again, only shown when `loopType` is **not** `"all"` and there are `loop_metadata` entries.

For each metadata rule, the user sees:

- The arrow-like symbol.
- A red **X button** to remove this metadata rule.
- A small dropdown with **metadata fields** (from `tableMetadataOptions`), each with a label (for example “File Name”, “Source System”, etc.).
- A checkbox labeled via tooltip “Ignore Value”.

The user configures:

1. **Which metadata field to use** (via the dropdown).
2. Whether to **“Ignore Value”** for that field (via the checkbox).

### How this relates to the backend

Each selection builds an entry like:

```js
profile.tables[index].table['loop_metadata'][op_index] = {
  metadata: "...",   // packed info: index:key:tableIndex
  ignoreValue: true/false
}
```

In the backend, this connects to:

```python
loop_metadata = self.profile_output_tables[index]['table'].get('loop_metadata', [])
for metadata in loop_metadata:
    key = metadata.get('value')
    ignoreValue = metadata.get('ignoreValue')
    table = metadata.get('table')
```

The backend then:

- Uses `key` and `table` to identify the metadata field and (if needed) a reference table.
- If **Ignore Value is checked**:
  - The backend only checks if the current input table has this metadata key at all.
- If **Ignore Value is not checked**:
  - The backend compares the metadata value in the current table with the value from the reference table.
  - If they differ, the table does *not* join the loop.

**Effect:**  
You are telling the system:  
“Group tables in this loop based on this metadata field: either they just need to have it, or they need to have the same value.”

The checkbox determines whether you require **presence** of the field or **exact matching value**.

---

## 4. Text/Pattern-based rules: `loop_theader` (for “same table header”)

```jsx
{profile.tables[index].loopType !== "all" &&
 profile.tables[index].table['loop_theader'] &&
 profile.tables[index].table['loop_theader'].map((operation, op_index) => (
  <InputGroup>
    <InputGroup.Text>&#8627;</InputGroup.Text>
    <Button
      variant="outline-danger"
      onClick={() => this.removeOperation(index, 'loop_theader', op_index)}
    >
      &times;
    </Button>
    <Form.Control
      value={operation.line || ''}
      placeholder='Line'
      onChange={(event) => {
        this.updateOperation(index, 'loop_theader', op_index, 'line', event.target.value)
      }}
    />
    <Form.Control
      value={operation.regex || ''}
      placeholder='Regex'
      onChange={(event) => {
        this.updateOperation(index, 'loop_theader', op_index, 'regex', event.target.value)
      }}
    />
  </InputGroup>
))}
```

### What the user sees

Only shown when `loopType` is **not** `"all"` and there are `loop_theader` rules.

For each rule, the user sees:

- The arrow-like symbol.
- A red **X button** to remove the rule.
- A text input labeled by placeholder **“Line”**.
- A text input labeled by placeholder **“Regex”** (regular expression; a text pattern).

The user enters:

- A line indicator (for example which line or section to look at in the table header).
- A pattern (regex) that describes what text should appear there.

### How this relates to the backend

Each rule is stored as something like:

```js
profile.tables[index].table['loop_theader'][op_index] = {
  line: '...',
  regex: '...'
}
```

In the backend, `_check_loop_condition` does:

```python
loop_theader = self.profile_output_tables[index]['table'].get('loop_theader', [])
for theader in loop_theader:
    match, _ = self._search_regex(theader, input_table_index)
    if match is None:
        return False
```

This means:

- For each rule, it runs a search (with `_search_regex`) on the current input table.
- If the pattern is **not** found in the specified line or area, the table fails the condition.

**Effect:**  
You are telling the system:  
“Only use input tables in this loop if their header text matches this pattern at this line/position.”

This is a flexible way to match based on specific text in the table header.

---

## Putting it all together

From the user’s perspective:

1. **Choose how the output table should loop:**
   - For all tables,
   - Or only for tables that share the same column headers,
   - Or share the same table header text,
   - Or share certain metadata.

2. **If you choose anything other than “all”:**
   - Additional configuration fields appear:
     - For **column header** loops, you pick the column(s) that must match.
     - For **metadata** loops, you pick the metadata field(s) and whether to require the same value or just the presence of the field.
     - For **table header** loops, you specify header lines and text patterns that must be found.

From the backend’s perspective:

- Your choices fill `loopType`, `loop_header`, `loop_metadata`, and `loop_theader` inside `profile_output_tables`.
- `_has_loop` and `_check_loop_condition` then use exactly those fields to decide:
  - Whether a loop exists, and
  - Which input tables fulfill the conditions and belong to that loop.

In short:  
The frontend elements you see are a user-friendly way to configure the rules that the backend code enforces when grouping input tables into repeated output tables.
