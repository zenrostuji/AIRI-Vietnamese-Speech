$h = @{Authorization="Bearer airi-local"}
Invoke-RestMethod "http://127.0.0.1:23333/health"
Invoke-RestMethod "http://127.0.0.1:23333/v1/models" -Headers $h
Invoke-RestMethod "http://127.0.0.1:23333/v1/voices" -Headers $h
$status = Invoke-RestMethod "http://127.0.0.1:23333/api/connection-status" -Headers $h
$status | ConvertTo-Json -Depth 4

Write-Host "`nTTS smoke test..."
$body = @{model="vieneu-tts-v3-turbo"; input="Xin chào AIRI"; voice="truc-ly"; response_format="wav"} | ConvertTo-Json
Invoke-WebRequest "http://127.0.0.1:23333/v1/audio/speech" -Method Post -Headers $h -ContentType "application/json" -Body $body -OutFile "$env:TEMP\airi-speech-test.wav"
Write-Host "Saved: $env:TEMP\airi-speech-test.wav"
