# CEASER Desktop Companion - Installer Test Report

Build: `CEASER Setup 0.1.1.exe`  
Tester: ____________________  
Device: ____________________  
Windows version: ____________________  
Date: ____________________

Use `PASS`, `FAIL`, `BLOCKED`, or `NOT TESTED`. Capture the command, transcript,
route, provider, response, duration, and relevant log lines for every failure.

## 1. Installation And Startup

1. Install CEASER in the default directory.
2. Install CEASER in a custom directory.
3. Launch from the installer completion screen.
4. Launch from the desktop shortcut.
5. Launch from the Start menu.
6. Restart CEASER and verify the account session persists.
7. Restart Windows and verify CEASER starts correctly.
8. Verify only one Electron and one Python companion session are active.
9. Verify the overlay opens and does not block clicks outside its visible UI.
10. Verify logs are created under the CEASER application-data directory.

## 2. Account And Device Connection

1. Connect your CEASER account.
2. Complete login while already signed into the website.
3. Complete login after being redirected through web sign-in.
4. Cancel the approval page and retry.
5. Close the browser during approval and retry.
6. Restart CEASER after connecting.
7. Confirm the device appears in Connected Devices.
8. Confirm device name, version, platform, and last-active time are correct.
9. Revoke the device from the website and verify the desktop reconnect screen appears.
10. Disconnect the network temporarily and verify local commands still work.

## 3. Hotkey, Listening, And Speech

Use `Ctrl+Shift+Space` unless the installed build displays another configured hotkey.

1. Trigger the hotkey once and say `Open Calculator`.
2. Trigger it repeatedly ten times, completing one command per activation.
3. Wait silently for ten seconds, then speak a command.
4. Speak immediately after triggering the hotkey.
5. Speak slowly with pauses between words.
6. Speak while music is playing and verify media ducks only during capture.
7. Verify media volume returns to its previous level after execution.
8. Interrupt CEASER speech with `stop`.
9. Interrupt CEASER speech with a new command.
10. Verify CEASER does not trigger itself while speaking.
11. Say `repeat` and verify the last response is repeated.
12. Say `be brief`, then ask an explanation question.
13. Say `explain more`, then ask a follow-up.
14. Verify one spoken command produces exactly one execution.
15. Verify the terminal/log file records STT provider, transcript, route, response, and timestamps.

## 4. Application Control

1. `Open Calculator`
2. `Open Notepad`
3. `Open Chrome`
4. `Open Microsoft Edge`
5. `Open File Explorer`
6. `Open Windows Settings`
7. `Open Task Manager`
8. `Open Paint`
9. `Open Command Prompt`
10. `Open PowerShell`
11. `Open Visual Studio Code`
12. `Switch to Chrome`
13. `Switch to Notepad`
14. `Switch back to Chrome`
15. `Close Calculator`
16. `Close Notepad`
17. `Close Chrome`
18. `Minimize this window`
19. `Maximize this window`
20. `Restore this window`

Expected: an already-open application is focused instead of duplicated unless the
user explicitly asks for a new window or profile.

## 5. Windows And Hardware Actions

1. `Set volume to 30 percent`
2. `Increase the volume`
3. `Decrease the volume`
4. `Mute the volume`
5. `Unmute the volume`
6. `Set brightness to 50 percent`
7. `Increase screen brightness`
8. `Decrease screen brightness`
9. `Take a screenshot`
10. `Open the Downloads folder`
11. `Open the Documents folder`
12. `Open the Desktop folder`
13. `Lock the screen` - confirmation required where configured.
14. `Shut down the computer` - verify confirmation; cancel it.
15. `Restart the computer` - verify confirmation; cancel it.

## 6. Browser And Search

1. `Search Google for artificial intelligence news`
2. `Open youtube.com`
3. `Open github.com in a new tab`
4. `Search YouTube for relaxing music`
5. `Play Believer on YouTube`
6. `Play Believer in a new tab`
7. `Close the YouTube tab`
8. `Close the GitHub tab`
9. `Switch to the previous tab`
10. `Switch to the next tab`
11. `Go back`
12. `Go forward`
13. `Refresh this page`
14. `Scroll down`
15. `Scroll up`
16. `Open Chrome using my Work profile` - replace `Work` with a real profile.
17. `Open Chrome using my Personal profile` - replace `Personal` with a real profile.

## 7. Media Control

1. `Play Believer`
2. `Pause music`
3. `Play music` - must resume the same paused media.
4. `Pause music`, then `resume music`.
5. `Pause music`, then `continue`.
6. `Play Arijit Singh` - explicit target starts new playback.
7. `Play some jazz` - explicit discovery request starts new playback.
8. `Next track`
9. `Previous track`
10. `Forward ten seconds`
11. `Rewind ten seconds`
12. `Stop music`
13. With no media active, say `play music` and verify generic playback behavior.

## 8. General AI And Continuation

1. `Explain quantum computing simply.`
2. `Summarize.`
3. `Make it shorter.`
4. `Explain more.`
5. `Why?`
6. `Continue.`
7. `Tell me more.`
8. `What about quantum computers in India?`
9. `Explain the second point.`
10. `Rewrite that professionally.`
11. `Translate that into Hindi.`
12. `Now open Calculator.` - must become a new desktop command.
13. `Are you male or female?`
14. `What can you help me with?`
15. `What is my name?` - requires a connected account profile.

Expected: short follow-ups use the immediate conversation, while explicit new
commands leave the previous topic.

## 9. Coding And Bolt Routing

1. `Write HTML and CSS for an animated login page.`
2. `Create a responsive portfolio page using HTML, CSS, and JavaScript.`
3. `Write a Python expense tracker.`
4. `Create a React login component with validation.`
5. `Generate a REST API endpoint using FastAPI.`
6. `Write a Java program to sort a list.`
7. `Create a SQL query for monthly sales totals.`
8. `Explain and fix this JavaScript error: Cannot read properties of undefined.`
9. `Add unit tests for this function.`
10. `Refactor this code for readability.`

Expected logs: `agents=Bolt`; NVIDIA Nemotron is preferred, Hugging Face is the
next coding provider, and OpenAI/Groq are fallback providers. Code must finish,
remain fenced, show its language, and provide a working Copy button. Coding
responses must not include unrelated web images.

## 10. Visual And Web Research Eligibility

1. `Explain quantum physics.` - no images expected.
2. `Write a professional leave email.` - no images expected.
3. `Create a seven-day study plan.` - no images expected.
4. `Show images of Indian fighter aircraft.` - relevant images expected.
5. `What war machines does India have?` - relevant images may appear.
6. `Show photos of places to visit in Hyderabad.` - relevant images expected.
7. `Summarize recent AI news.` - sources expected; images only when materially useful.
8. Open every source link and verify it points to the external source, not CEASER's own URL.

## 11. Files And Smart Capture

1. Drop a PDF and select `Summarize this document`.
2. Select `Extract key points`.
3. Select `Find dates and deadlines`.
4. Select `Explain in simple words`.
5. Ask `Explain page 2.`
6. Ask `Create quiz questions from this.`
7. Drop a DOCX and summarize it.
8. Drop an XLSX and request a table analysis.
9. Drop a PPTX and summarize its slides.
10. Drop a JPG/PNG containing text and verify OCR is used.
11. Drop an unsupported file and verify a clear safe error.
12. Attempt to attach `.env` and verify it is blocked.

## 12. Cloud Resources

1. `List my CEASER files.`
2. `What is my latest document?`
3. `Read my latest report.`
4. `Search my files for architecture.`
5. `Open my CEASER proposal.`
6. `Upload this file.` - use a disposable file and confirm.
7. `Rename this document.` - confirmation required.
8. `Delete my latest test report.` - use disposable data; confirmation required.
9. Answer `no` and verify deletion does not occur.
10. Repeat, answer `yes`, and verify soft deletion.
11. `Restore the deleted test report.` - confirmation required.
12. Disconnect the network and retry a cloud read; verify the account stays connected.

## 13. GitHub Integration

1. `List my GitHub repositories.`
2. `Summarize my GitHub repositories.`
3. `Find repositories related to <keyword>.`
4. `Show recent commits in <repository>.`
5. `Summarize the README in <repository>.`
6. `Show open issues in <repository>.`
7. `Show open pull requests in <repository>.`
8. `What languages are used in <repository>?`
9. `Show the latest commit in <repository>.`
10. `Explain the folder structure of <repository>.`

Replace placeholders with repositories visible to the connected user. No repository
names or account identity should be hardcoded.

## 14. Notion Integration

1. `List my latest Notion pages.`
2. `Summarize my Notion workspace structure.`
3. `Show my Notion databases.`
4. `Summarize the page named <page name>.`
5. `Find Notion pages about <keyword>.`
6. `Show tasks in my Tasks database.`
7. `Show tasks assigned to <member name>.`
8. `Create a task called Desktop beta review.` - confirmation required.
9. `Assign Desktop beta review to <member name>.` - confirmation required.
10. `Update Desktop beta review to completed.` - confirmation required.

## 15. Suggestions, Confirmation, And Safety

1. Open a repository and verify at most one useful next-action suggestion appears.
2. Answer `yes` and verify only the bound suggestion executes.
3. Answer `not now` and verify the suggestion clears.
4. Start a protected action and verify confirmation outranks suggestions.
5. Say `cancel` during confirmation and verify nothing executes.
6. Say `yes` twice and verify no duplicate execution occurs.
7. Trigger an unknown desktop action and verify CEASER asks or fails safely.
8. Verify secrets, access tokens, API keys, and private transcripts never appear in logs.

## 16. Recovery And Endurance

1. Reload the Electron renderer and verify Python remains/reconnects safely.
2. Stop the Python child process and verify controlled restart.
3. Disconnect and reconnect the microphone.
4. Sleep and resume Windows.
5. Disconnect and reconnect the network.
6. Let CEASER remain idle for 30 minutes, then issue a command.
7. Run 25 voice commands and verify zero duplicate executions.
8. Run 25 typed commands and verify no growing latency or stuck state.
9. Interrupt TTS five times and verify listening always recovers.
10. Exit CEASER and verify Electron/Python shut down cleanly.

## Result Summary

| Area | Passed | Failed | Blocked | Notes |
|---|---:|---:|---:|---|
| Install/startup | | | | |
| Account/device | | | | |
| Voice/STT/TTS | | | | |
| Desktop actions | | | | |
| Browser/media | | | | |
| Conversation | | | | |
| Bolt coding | | | | |
| Visual research | | | | |
| Files/cloud | | | | |
| GitHub/Notion | | | | |
| Safety/recovery | | | | |

## Failure Record

| ID | Command | Expected | Actual | Duration | Log timestamp | Status |
|---|---|---|---|---:|---|---|
| 1 | | | | | | |

## Release Verdict

- [ ] PASS - suitable for public beta
- [ ] CONDITIONAL PASS - only documented non-critical issues remain
- [ ] FAIL - one or more launch blockers remain

Launch blockers include crashes, account crossover, secret exposure, duplicate
execution, confirmation bypass, destructive action without confirmation, unusable
voice capture, or coding responses routed outside the verified Bolt path.
