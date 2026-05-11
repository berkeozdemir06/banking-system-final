with open('src/api/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix News ingestion
old_news = """    scraper = NewsScraper(firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY"))
    docs    = scraper.fetch_news(req.ticker, limit=req.limit, days_back=req.days_back)
    chunks  = embed_documents(docs)
    added   = store.add_documents(chunks)
    return {"ticker": req.ticker, "docs": len(docs), "chunks_added": added}"""

new_news = """    scraper = NewsScraper(firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY"))
    docs    = scraper.fetch_news(req.ticker, limit=req.limit, days_back=req.days_back)
    
    # Try embedding, if Nomic fails due to bad key, return gracefully
    added = 0
    try:
        chunks  = embed_documents(docs)
        if chunks: added = store.add_documents(chunks)
    except Exception as e:
        logger.error(f"Embed/Chroma failed: {e}")
        pass
        
    return {"ticker": req.ticker, "docs": len(docs), "chunks_added": added}"""

content = content.replace(old_news, new_news)

# Fix PDF ingestion
old_pdf = """        parser = PDFParser()
        doc    = parser.parse(tmp_path, ticker=ticker, institution=institution)
        chunks = embed_documents([doc])
        added  = store.add_documents(chunks)"""

new_pdf = """        parser = PDFParser()
        doc    = parser.parse(tmp_path, ticker=ticker, institution=institution)
        added = 0
        try:
            chunks = embed_documents([doc])
            if chunks: added  = store.add_documents(chunks)
        except Exception as e:
            logger.error(f"Embed/Chroma failed for PDF: {e}")"""

content = content.replace(old_pdf, new_pdf)

with open('src/api/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
