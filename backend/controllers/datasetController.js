import {
  getUserDatasets,
  getDatasetById,
  deleteDataset,
  createDataset,
} from "../services/datasetService.js";

import { parseFile } from "../utils/fileParser.js";
import { analyzeData } from "../utils/dataAnalyzer.js";

export const uploadDataset = async (req, res, next) => {
  try {
    if (!req.file) {
      const error = new Error("Please upload a file");
      error.statusCode = 400;
      throw error;
    }

    const rows = parseFile(
      req.file.path,
      req.file.originalname
    );

    const analysis = analyzeData(rows);

    const dataset = await createDataset({
      userId: req.user.userId,
      name: req.file.originalname,
      originalFileName: req.file.originalname,
      fileType: req.file.mimetype,
      fileSize: req.file.size,
      filePath: req.file.path,
      rowCount: analysis.rowCount,
      columnCount: analysis.columnCount,
      columns: analysis.columns,
    });

    res.status(201).json({
      success: true,
      message: "Dataset uploaded successfully",
      dataset,
    });
  } catch (error) {
    next(error);
  }
};

export const getDatasets = async (req, res, next) => {
  try {
    const datasets = await getUserDatasets(req.user.userId);

    res.status(200).json({
      success: true,
      count: datasets.length,
      datasets,
    });
  } catch (error) {
    next(error);
  }
};

export const getDataset = async (req, res, next) => {
  try {
    const dataset = await getDatasetById(
      req.params.id,
      req.user.userId
    );

    res.status(200).json({
      success: true,
      dataset,
    });
  } catch (error) {
    next(error);
  }
};

export const removeDataset = async (req, res, next) => {
  try {
    await deleteDataset(
      req.params.id,
      req.user.userId
    );

    res.status(200).json({
      success: true,
      message: "Dataset deleted successfully",
    });
  } catch (error) {
    next(error);
  }
};
export const getDatasetQuality = async (req, res, next) => {
  try {
    const dataset = await getDatasetById(
      req.params.id,
      req.user.userId
    );

    if (!dataset.filePath) {
      const error = new Error("Dataset file path is unavailable");
      error.statusCode = 400;
      throw error;
    }

    const agentUrl = (
      process.env.PYTHON_AGENT_URL || "http://127.0.0.1:8001"
    ).replace(/\/$/, "");

    const agentResponse = await fetch(`${agentUrl}/quality`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        csv_path: dataset.filePath,
      }),
      signal: AbortSignal.timeout(60000),
    });

    const result = await agentResponse.json();

    if (!agentResponse.ok) {
      const error = new Error(
        result.detail || "Failed to generate data quality report"
      );
      error.statusCode = agentResponse.status;
      throw error;
    }

    res.status(200).json({
      success: true,
      datasetId: dataset._id,
      datasetName: dataset.name,
      report: result.report,
    });
  } catch (error) {
    if (error.name === "TimeoutError") {
      error.statusCode = 504;
      error.message = "Data quality analysis timed out";
    }

    next(error);
  }
};