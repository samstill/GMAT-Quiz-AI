# Create a quiz named "Verbal Practice" through the API
$quizData = @{
    name = "Verbal Practice"
    description = "Practice for the GMAT Verbal section"
    time_limit = 60
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/quizzes/" -Method Post -Body $quizData -ContentType "application/json"

# Check if the quiz was created
Write-Host "`nChecking if the quiz was created:"
Invoke-RestMethod -Uri "http://localhost:8000/api/quizzes/" -Method Get
