import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(
            "http://localhost:11434/api/chat",
            json={
                "model":"llama3",
                "messages":[
                    {
                        "role":"user",
                        "content":"Return JSON {\"a\":1}"
                    }
                ],
                "format":"json",
                "stream":False
            }
        )

        print(r.status_code)
        print(r.text)

asyncio.run(main())