# CRUD curl examples

Run the API on port 8000 before using these commands.

```bash
curl -i http://localhost:8000/tasks

curl -i http://localhost:8000/tasks/1

curl -i -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d '{"title":"Buy milk"}'

curl -i -X PUT http://localhost:8000/tasks/4 -H "Content-Type: application/json" -d '{"title":"Buy oat milk","done":true}'

curl -i -X DELETE http://localhost:8000/tasks/4
```
