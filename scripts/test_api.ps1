$h = @{Authorization="Bearer airi-local"}
Invoke-RestMethod "http://127.0.0.1:23333/health"
Invoke-RestMethod "http://127.0.0.1:23333/v1/models" -Headers $h
Invoke-RestMethod "http://127.0.0.1:23333/v1/voices" -Headers $h
