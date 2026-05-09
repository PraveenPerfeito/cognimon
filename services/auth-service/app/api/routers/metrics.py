from fastapi import APIRouter, HTTPException, Request, Response, status

router = APIRouter()


@router.get("", include_in_schema=False)
async def scrape_metrics(request: Request) -> Response:
    metrics = request.app.state.metrics
    if metrics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metrics are disabled.",
        )

    payload, content_type = metrics.render()
    return Response(content=payload, media_type=content_type)
