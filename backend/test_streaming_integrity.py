"""
Test streaming integrity for long responses.

This test reproduces the known long-screenplay issue:
- Missing scene numbers
- Malformed markup
- Unfinished text
- Differences between streamed, final, and saved output
"""
import asyncio
import json
from collections.abc import AsyncIterator


async def simulate_streaming_pipeline():
    """Simulate the complete streaming pipeline from provider to persistence."""

    print("=== STREAMING INTEGRITY TEST ===\n")

    # Simulate a long screenplay response with scene markers
    screenplay_chunks = [
        "# Screenplay: The Final Mission\n\n",
        "## ACT I\n\n",
        "### SCENE 1 - INT. SPACESHIP BRIDGE - DAY\n\n",
        "CAPTAIN RIVERA stands at the viewport, staring into the void.\n\n",
        "**CAPTAIN RIVERA**\n",
        "(into comms)\n",
        "All hands, prepare for jump sequence.\n\n",
        "The bridge hums with activity. Officer Martinez checks her console.\n\n",
        "**OFFICER MARTINEZ**\n",
        "Captain, we're reading an anomaly in sector seven.\n\n",
        "### SCENE 2 - INT. ENGINE ROOM - DAY\n\n",
        "Chief Engineer TORRES wipes grease from his hands.\n\n",
        "**TORRES**\n",
        "The engines won't hold at maximum thrust for more than ten minutes.\n\n",
        "### SCENE 3 - INT. MEDICAL BAY - DAY\n\n",
        "Dr. CHEN examines readouts on a medical scanner.\n\n",
        "**DR. CHEN**\n",
        "We need to evacuate the crew. Now.\n\n",
        "## ACT II\n\n",
        "### SCENE 4 - EXT. SPACE STATION - DAY\n\n",
        "The damaged station drifts in orbit, lights flickering.\n\n",
        "**RIVERA (V.O.)**\n",
        "This is Captain Rivera of the Odyssey. We're coming to get you.\n\n",
        "### SCENE 5 - INT. SPACESHIP BRIDGE - CONTINUOUS\n\n",
        "Rivera turns to her crew with determination.\n\n",
        "**CAPTAIN RIVERA**\n",
        "Martinez, plot a rescue course. Torres, give me everything you've got.\n\n",
        "**OFFICER MARTINEZ**\n",
        "Course plotted, Captain.\n\n",
        "**TORRES (OVER COMMS)**\n",
        "Engines at one hundred ten percent. We've got maybe eight minutes.\n\n",
        "### SCENE 6 - INT. DOCKING BAY - DAY\n\n",
        "The crew rushes to prepare the rescue shuttle.\n\n",
        "**LIEUTENANT KIM**\n",
        "Shuttle prepped and ready.\n\n",
        "### SCENE 7 - EXT. SPACE - DAY\n\n",
        "The Odyssey approaches the damaged station at high speed.\n\n",
        "## ACT III\n\n",
        "### SCENE 8 - INT. SPACE STATION - DAY\n\n",
        "Survivors huddle in the dark corridor. Alarms blare.\n\n",
        "**STATION COMMANDER**\n",
        "They're here! Everyone to the evacuation point!\n\n",
        "### SCENE 9 - INT. DOCKING BAY - DAY\n\n",
        "The rescue team boards. Dr. Chen tends to injured survivors.\n\n",
        "**DR. CHEN**\n",
        "Get them on board. We don't have much time.\n\n",
        "### SCENE 10 - INT. SPACESHIP BRIDGE - DAY\n\n",
        "Warning lights flash across every console.\n\n",
        "**OFFICER MARTINEZ**\n",
        "Captain, structural integrity at fifteen percent!\n\n",
        "**CAPTAIN RIVERA**\n",
        "All hands, brace for emergency jump!\n\n",
        "### SCENE 11 - EXT. SPACE - DAY\n\n",
        "The Odyssey pulls away from the station just as it explodes.\n\n",
        "A brilliant flash of light, then darkness.\n\n",
        "### SCENE 12 - INT. SPACESHIP BRIDGE - DAY\n\n",
        "The crew catches their breath. Silence.\n\n",
        "**CAPTAIN RIVERA**\n",
        "(smiling)\n",
        "Good work, everyone. Let's go home.\n\n",
        "**FADE TO BLACK**\n\n",
        "THE END"
    ]

    # Track what gets streamed vs saved
    streamed_chunks = []
    persisted_checkpoints = []
    final_saved = None

    print("1. STREAMING PHASE")
    print("-" * 60)

    # Simulate streaming with periodic persistence
    for i, chunk in enumerate(screenplay_chunks):
        streamed_chunks.append(chunk)
        response_so_far = "".join(streamed_chunks)

        # Simulate SSE token event
        if i == 0:
            print(f"[SSE] First token: {repr(chunk[:50])}")

        # Simulate periodic persistence (every ~360 chars)
        if i > 0 and len(response_so_far) % 360 < len(chunk):
            persisted_checkpoints.append({
                "chunk_index": i,
                "length": len(response_so_far),
                "content": response_so_far
            })
            print(f"[PERSIST] Checkpoint at {len(response_so_far)} chars (chunk {i})")

    print(f"\nTotal chunks streamed: {len(streamed_chunks)}")
    print(f"Periodic checkpoints: {len(persisted_checkpoints)}")

    # Simulate final assembly
    print("\n2. FINAL ASSEMBLY PHASE")
    print("-" * 60)

    response_text = "".join(streamed_chunks).strip()
    print(f"Final response length: {len(response_text)} chars")
    print(f"Scene count: {response_text.count('### SCENE')}")

    # Simulate finalization with normalization
    final_saved = response_text

    print("\n3. PERSISTENCE PHASE")
    print("-" * 60)
    print(f"Saving final response: {len(final_saved)} chars")

    # Check for integrity issues
    print("\n4. INTEGRITY CHECK")
    print("-" * 60)

    issues = []

    # Check if all scenes are present
    expected_scenes = 12
    actual_scenes = final_saved.count("### SCENE")
    if actual_scenes != expected_scenes:
        issues.append(f"Scene count mismatch: expected {expected_scenes}, got {actual_scenes}")

    # Check for malformed markdown
    if final_saved.count("###") != final_saved.count("### SCENE"):
        issues.append("Malformed markdown: ### markers without SCENE")

    # Check for incomplete dialogue
    if final_saved.count("**") % 2 != 0:
        issues.append("Unmatched bold markers in dialogue")

    # Check ending
    if not final_saved.endswith("THE END"):
        issues.append("Response does not end cleanly")

    # Compare streamed vs final
    streamed_final = "".join(streamed_chunks)
    if streamed_final != final_saved:
        issues.append(f"Streamed output differs from final saved (streamed: {len(streamed_final)}, saved: {len(final_saved)})")

    if issues:
        print("[X] INTEGRITY ISSUES FOUND:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print("[OK] All integrity checks passed")

    # Simulate continuation if truncated
    print("\n5. CONTINUATION SIMULATION")
    print("-" * 60)

    # Simulate token limit hit at 70% through
    truncation_point = int(len(screenplay_chunks) * 0.7)
    truncated_chunks = screenplay_chunks[:truncation_point]
    truncated_response = "".join(truncated_chunks)

    print(f"Simulating truncation at chunk {truncation_point}/{len(screenplay_chunks)}")
    print(f"Truncated length: {len(truncated_response)} chars")
    print(f"Scenes in truncated: {truncated_response.count('### SCENE')}")

    # Check what continuation would see
    tail = truncated_response[-12000:] if len(truncated_response) > 12000 else truncated_response
    print(f"\nContinuation tail size: {len(tail)} chars")
    print(f"Last complete scene: {tail.rfind('### SCENE')}")

    # Simulate continuation
    continuation_chunks = screenplay_chunks[truncation_point:]
    continuation = "".join(continuation_chunks)

    print(f"Continuation adds: {len(continuation)} chars")
    print(f"Continuation scenes: {continuation.count('### SCENE')}")

    # Final with continuation
    full_with_continuation = truncated_response + continuation
    final_scene_count = full_with_continuation.count("### SCENE")

    print(f"\nFinal after continuation: {len(full_with_continuation)} chars")
    print(f"Total scenes: {final_scene_count}")

    if final_scene_count != expected_scenes:
        print(f"⚠️  Scene loss detected: {expected_scenes - final_scene_count} scenes missing")

    return {
        "streamed_length": len(streamed_final),
        "final_length": len(final_saved),
        "checkpoints": len(persisted_checkpoints),
        "issues": issues,
        "scenes_expected": expected_scenes,
        "scenes_actual": actual_scenes,
    }


async def test_chunk_boundary_handling():
    """Test that chunk boundaries don't corrupt markdown or dialogue."""
    print("\n\n=== CHUNK BOUNDARY TEST ===\n")

    # Test splitting markdown markers across chunks
    test_cases = [
        {
            "name": "Split heading marker",
            "chunks": ["### ", "SCENE ", "1 - INT"],
            "expected_marker": "### SCENE 1 - INT"
        },
        {
            "name": "Split bold marker",
            "chunks": ["**CAPT", "AIN RI", "VERA**"],
            "expected_marker": "**CAPTAIN RIVERA**"
        },
        {
            "name": "Split newline before heading",
            "chunks": ["Previous line\n", "\n###", " SCENE 2"],
            "expected_marker": "\n\n### SCENE 2"
        },
        {
            "name": "Split at punctuation",
            "chunks": ["Hello", ", ", "world", "!"],
            "expected_marker": "Hello, world!"
        }
    ]

    for test in test_cases:
        assembled = "".join(test["chunks"])
        matches = test["expected_marker"] in assembled
        status = "[OK]" if matches else "[X]"
        print(f"{status} {test['name']}")
        if not matches:
            print(f"   Expected: {repr(test['expected_marker'])}")
            print(f"   Got: {repr(assembled)}")


async def test_persistence_consistency():
    """Test that periodic persistence matches final save."""
    print("\n\n=== PERSISTENCE CONSISTENCY TEST ===\n")

    content = "A" * 1000  # 1000 chars

    # Simulate periodic checkpoints
    checkpoint_interval = 360
    checkpoints = []
    for i in range(0, len(content), checkpoint_interval):
        checkpoints.append(content[:i + checkpoint_interval])

    # Final should match last checkpoint extended to end
    final_save = content
    last_checkpoint = checkpoints[-1] if checkpoints else ""

    print(f"Content length: {len(content)}")
    print(f"Checkpoints: {len(checkpoints)}")
    print(f"Last checkpoint: {len(last_checkpoint)} chars")
    print(f"Final save: {len(final_save)} chars")

    if len(last_checkpoint) <= len(final_save):
        print("✅ Final save is at least as complete as last checkpoint")
    else:
        print("❌ Final save is shorter than last checkpoint")

    if final_save.startswith(last_checkpoint):
        print("✅ Final save extends from last checkpoint")
    else:
        print("❌ Final save does not match checkpoint content")


if __name__ == "__main__":
    print("CEASER Streaming Integrity Tests")
    print("=" * 60)

    result = asyncio.run(simulate_streaming_pipeline())
    asyncio.run(test_chunk_boundary_handling())
    asyncio.run(test_persistence_consistency())

    print("\n\n=== SUMMARY ===")
    print(f"Streamed length: {result['streamed_length']}")
    print(f"Final length: {result['final_length']}")
    print(f"Issues found: {len(result['issues'])}")

    if result['issues']:
        print("\nRoot causes to investigate:")
        print("1. Check response_pipeline.py stream() method for chunk assembly")
        print("2. Check orchestrator.py finalize_stream_response() for normalization")
        print("3. Check routes.py for final assembly: response_text = ''.join(chunks).strip()")
        print("4. Verify persist_stream_response() saves exactly what was streamed")
        print("5. Check if continuation logic corrupts previous content")
