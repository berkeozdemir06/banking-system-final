import asyncio
from src.ingestion.kap_intelligence import full_analysis

async def main():
    res = await full_analysis("TRENJ", kap_limit=10)
    print(f"Announcements: {len(res['announcements'])}")
    if res['announcements']:
        print(res['announcements'][0]['title'])

if __name__ == '__main__':
    asyncio.run(main())
