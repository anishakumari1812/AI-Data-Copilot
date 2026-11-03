from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent.graphh import copilot_graph
from agent.quality_service import profile_csv

load_dotenv()

app = FastAPI(title="AI Data Copilot Agent API")


class CopilotRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    csv_path: str = Field(min_length=1)


class QualityRequest(BaseModel):
    csv_path: str = Field(min_length=1)


@app.get("/health")
def health():
    return {
        "success": True,
        "service": "AI Data Copilot Agent",
    }


@app.post("/ask")
def ask_copilot(request: CopilotRequest):
    csv_file = Path(request.csv_path).expanduser().resolve()

    if not csv_file.is_file():
        raise HTTPException(
            status_code=404,
            detail="Dataset file not found",
        )

    if csv_file.suffix.lower() != ".csv":
        raise HTTPException(
            status_code=400,
            detail="The SQL agent currently supports CSV datasets only",
        )

    try:
        df = pd.read_csv(csv_file, nrows=1000)

        if len(df.columns) == 0:
            raise ValueError("CSV has no columns")

        schema = (
            "Table: dataset\nColumns:\n"
            + "\n".join(
                f"- {column} ({dtype})"
                for column, dtype in df.dtypes.items()
            )
        )

        result = copilot_graph.invoke({
            "question": request.question.strip(),
            "csv_path": str(csv_file),
            "schema": schema,
        })

        if result.get("error"):
            raise HTTPException(
                status_code=502,
                detail=result["error"],
            )

        return {
            "success": True,
            "question": request.question.strip(),
            "sqlQuery": result["sql_query"],
            "queryResult": result["query_result"],
            "answer": result["final_answer"],
        }

    except HTTPException:
        raise

    except Exception as exc:
        print("Agent API error:", str(exc))
        raise HTTPException(
            status_code=500,
            detail="Failed to process the dataset question",
        ) from exc


@app.post("/quality")
def get_data_quality(request: QualityRequest):
    try:
        report = profile_csv(request.csv_path)

        return {
            "success": True,
            "report": report,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        print("Data quality error:", str(exc))
        raise HTTPException(
            status_code=500,
            detail="Failed to generate the data quality report",
        ) from exc
