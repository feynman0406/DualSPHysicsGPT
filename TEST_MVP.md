# Quick Test Guide for MVP

## Fastest Way to Test (Copy-Paste)

### Step 1: Set Environment Variables

**Windows (Command Prompt):**
```cmd
set OPENAI_API_KEY=your_actual_key_here
set OPENAI_RAG_VS_DESIGN_ID=vs_68cc41440b9c8191bb5ef0fce9c4417f
set OPENAI_MODEL=gpt-4o
```

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="your_actual_key_here"
$env:OPENAI_RAG_VS_DESIGN_ID="vs_68cc41440b9c8191bb5ef0fce9c4417f"
$env:OPENAI_MODEL="gpt-4o"
```

**Linux/Mac:**
```bash
export OPENAI_API_KEY=your_actual_key_here
export OPENAI_RAG_VS_DESIGN_ID=vs_68cc41440b9c8191bb5ef0fce9c4417f
export OPENAI_MODEL=gpt-4o
```

### Step 2: Run the MVP

```bash
python scripts/mvp_direct_file_search.py
```

### Step 3: Check Outputs

```bash
# View Agent 1 output (references found)
cat logs/mvp/agent1_output.json

# View Agent 2 output (generated config)
cat logs/mvp/agent2_config.json

# View final XML
cat logs/mvp/generated_case.xml
```

## What You Should See

### During Execution:

```
================================================================================
                           ENVIRONMENT CHECK                            
================================================================================

✓ OPENAI_API_KEY: ********************
✓ OPENAI_RAG_VS_DESIGN_ID: vs_68cc41440b9c8191...
✓ OPENAI_MODEL: gpt-4o

================================================================================
                  AGENT 1: REFERENCE FINDER (OpenAI File Search)                  
================================================================================

Query: Create a 2D dambreak simulation with water height 2 meters
Model: gpt-4o
Vector Store: vs_68cc41440b9c8191bb5ef0fce9c4417f

[Step 1/3] Searching vector store for relevant examples...
--------------------------------------------------------------------------------
✓ Found 3 reference files

[Step 2/3] Analyzing references...
--------------------------------------------------------------------------------
[Agent 1 will print its analysis here]

[Step 3/3] Preparing instructions for Agent 2...
--------------------------------------------------------------------------------

✓ Agent 1 complete
  - References found: 3
  - Output saved to: logs/mvp/agent1_output.json

================================================================================
                  AGENT 2: CONFIG GENERATOR (Strict JSON Schema)                  
================================================================================

[Step 1/3] Loading DualSPHysics JSON schema...
--------------------------------------------------------------------------------
✓ Schema loaded: dualsphysics_config_schema.json

[Step 2/3] Building prompt from Agent 1 references...
--------------------------------------------------------------------------------
✓ Prompt built (xxxx chars)

[Step 3/3] Generating config with strict schema enforcement...
--------------------------------------------------------------------------------
✓ Config generated (xx top-level keys)
✓ Agent 2 complete
  - Output saved to: logs/mvp/agent2_config.json

================================================================================
                           XML GENERATION & EXECUTION                           
================================================================================

[Step 1/2] Normalizing config...
--------------------------------------------------------------------------------
✓ No normalization warnings

[Step 2/2] Generating XML...
--------------------------------------------------------------------------------
✓ XML generated (xxxx chars)
  - Saved to: logs/mvp/generated_case.xml

================================================================================
                                   SUCCESS!                                   
================================================================================
Generated files:
  1. logs/mvp/agent1_output.json     - Agent 1 references & analysis
  2. logs/mvp/agent2_config.json     - Agent 2 generated config
  3. logs/mvp/generated_case.xml     - Final XML output

Workflow complete!
```

## Testing via API (Alternative)

The MVP script is standalone, but you can also test the **production two-stage system** via API:

### 1. Set Environment for Two-Stage Mode

```bash
# All the previous vars, plus:
export USE_TWO_STAGE_RAG_SCHEMA=1
export USE_RAG_PLANNING_AGENT=1
export USE_RAG=1
```

### 2. Start Server

```bash
uvicorn api.main:app --reload --port 8000
```

### 3. Test with POST Request

**Using curl:**
```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"query": "Create a 2D dambreak simulation"}'
```

**Using Python:**
```python
import requests
response = requests.post(
    'http://localhost:8000/run',
    json={'query': 'Create a 2D dambreak simulation'}
)
print(response.json())
```

**Using browser/Postman:**
- URL: `http://localhost:8000/run`
- Method: POST
- Headers: `Content-Type: application/json`
- Body: `{"query": "Create a 2D dambreak simulation"}`

### 4. Check Production System Logs

The production system saves to different location:
```bash
cat logs/last_run/planning_plan.json  # Plan JSON from production system
cat logs/last_run/metadata.json       # File search metadata
```

## Common Issues

### "Missing required environment variables"
- You forgot to set `OPENAI_API_KEY` or `OPENAI_RAG_VS_DESIGN_ID`
- Check: `echo $OPENAI_API_KEY` (Linux/Mac) or `echo %OPENAI_API_KEY%` (Windows)

### "ModuleNotFoundError: No module named 'openai'"
```bash
pip install openai
```

### "Vector store not found"
- Your `OPENAI_RAG_VS_DESIGN_ID` might be wrong
- Check in OpenAI dashboard: https://platform.openai.com/storage

### Script hangs at "Searching vector store"
- OpenAI API might be slow
- Wait 10-30 seconds
- Check your internet connection

### "Schema validation failed"
- Agent 2 couldn't generate valid config
- Check `logs/mvp/agent1_output.json` - were good references found?
- Try a simpler query first

## Testing Different Scenarios

### Test 1: Default Query (2D Dambreak)
```bash
python scripts/mvp_direct_file_search.py
```

### Test 2: 3D Dambreak
```bash
python scripts/mvp_direct_file_search.py --query "Create a 3D dambreak simulation"
```

### Test 3: Sloshing Tank
```bash
python scripts/mvp_direct_file_search.py --query "Create a sloshing tank simulation"
```

### Test 4: Floating Body
```bash
python scripts/mvp_direct_file_search.py --query "Create a simulation with a floating sphere"
```

### Test 5: Pause After Agent 1
```bash
python scripts/mvp_direct_file_search.py --pause-after-agent1
# This lets you inspect what Agent 1 found before continuing
```

## Next Steps After Testing

1. **Inspect Agent 1 output** - See what references it found
2. **Review Agent 2 config** - Check if schema is correctly populated
3. **Validate XML** - Ensure XML is well-formed
4. **Compare with examples** - Compare output to files in `AutoXml_script/config_library/`
5. **Report issues** - If something fails, check the error messages and logs

## For More Details

See `docs/MVP_USAGE.md` for complete documentation.
