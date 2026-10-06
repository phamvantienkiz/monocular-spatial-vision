"""Laser Ground Truth Benchmark API endpoints."""

from fastapi import APIRouter
from app.schemas.benchmark import LaserBenchmarkEntry, BenchmarkResult
from app.services.benchmark_service import BenchmarkService

router = APIRouter()
benchmark_service = BenchmarkService()


@router.post("/benchmark/record", response_model=BenchmarkResult)
def record_benchmark_sample(entry: LaserBenchmarkEntry):
    """Records a single laser comparison sample and calculates AbsRel error."""
    return benchmark_service.evaluate_entry(entry)


@router.get("/benchmark/summary")
def get_benchmark_summary():
    """Returns aggregated benchmark statistics and pass rates."""
    return benchmark_service.get_summary()
