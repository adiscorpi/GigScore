import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import dotenv from "dotenv";
import express from "express";
import OpenAI from "openai";
import { createServer as createViteServer } from "vite";

import { buildCreditReport, buildCreditReportHtml, buildCreditReportPdf } from "./reporting.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const execFileAsync = promisify(execFile);

dotenv.config({ path: path.join(__dirname, ".env.local"), override: false });
dotenv.config({ path: path.join(__dirname, ".env"), override: false });

const HOST = process.env.HOST || "127.0.0.1";
const PORT = Number(process.env.PORT || 5173);
const isProduction = process.env.NODE_ENV === "production";

function getProviderConfig() {
  const provider = (process.env.LLM_PROVIDER || "groq").toLowerCase();

  if (provider === "openai") {
    return {
      provider: "openai",
      apiKey: (process.env.OPENAI_API_KEY || "").trim(),
      baseURL: process.env.OPENAI_BASE_URL || undefined,
      model: process.env.OPENAI_MODEL || "gpt-5-mini",
      reasoningEffort: process.env.OPENAI_REASONING_EFFORT || "low",
      maxOutputTokens: Number(process.env.OPENAI_MAX_OUTPUT_TOKENS || 700),
      missingKeyMessage: "Risk Officer is not configured yet. Add OPENAI_API_KEY to .env.local and restart `npm run dev`.",
    };
  }

  return {
    provider: "groq",
    apiKey: (process.env.GROQ_API_KEY || "").trim(),
    baseURL: "https://api.groq.com/openai/v1",
    model: process.env.GROQ_MODEL || "openai/gpt-oss-20b",
    reasoningEffort: process.env.GROQ_REASONING_EFFORT || "low",
    maxOutputTokens: Number(process.env.GROQ_MAX_OUTPUT_TOKENS || 700),
    missingKeyMessage: "Risk Officer is not configured yet. Add GROQ_API_KEY to .env.local and restart `npm run dev`.",
  };
}

function getClient(config) {
  if (!config.apiKey) return null;

  return new OpenAI({
    apiKey: config.apiKey,
    baseURL: config.baseURL,
  });
}

function normalizeMessages(messages) {
  if (!Array.isArray(messages)) return [];

  return messages
    .filter((message) => message && typeof message.content === "string")
    .map((message) => ({
      role: message.role === "assistant" ? "assistant" : "user",
      content: message.content.trim(),
    }))
    .filter((message) => message.content.length > 0);
}

function getFriendlyError(error) {
  if (!error) return "Unknown server error.";
  if (typeof error.message === "string" && error.message.trim()) return error.message;
  return "The Risk Officer service could not complete the request.";
}

function getAgent5VoiceConfig(language = "en") {
  if (language === "hi") {
    return {
      voice: process.env.AGENT5_HINDI_VOICE || "Lekha",
      rate: Number(process.env.AGENT5_HINDI_RATE || 176),
    };
  }

  return {
    voice: process.env.AGENT5_ENGLISH_VOICE || "Rishi",
    rate: Number(process.env.AGENT5_ENGLISH_RATE || 182),
  };
}

async function buildAgent5VoiceAudio(text, language = "en") {
  const normalizedLanguage = language === "hi" ? "hi" : "en";
  const { voice, rate } = getAgent5VoiceConfig(normalizedLanguage);
  const id = `gigscore-agent5-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const aiffPath = path.join(os.tmpdir(), `${id}.aiff`);
  const wavPath = path.join(os.tmpdir(), `${id}.wav`);

  try {
    await execFileAsync("say", [
      "-v",
      voice,
      "-r",
      String(rate),
      "-o",
      aiffPath,
      text,
    ]);

    await execFileAsync("afconvert", [
      "-f",
      "WAVE",
      "-d",
      "LEI16@24000",
      aiffPath,
      wavPath,
    ]);

    const buffer = await fs.readFile(wavPath);
    return {
      buffer,
      voice,
      contentType: "audio/wav",
    };
  } finally {
    await Promise.allSettled([
      fs.unlink(aiffPath),
      fs.unlink(wavPath),
    ]);
  }
}

const app = express();

app.use(express.json({ limit: "1mb" }));

app.get("/api/health", (_req, res) => {
  const config = getProviderConfig();
  res.json({
    ok: true,
    provider: config.provider,
    configured: Boolean(config.apiKey),
    model: config.model,
  });
});

app.post("/api/risk-officer", async (req, res) => {
  const { systemPrompt, messages } = req.body ?? {};

  if (typeof systemPrompt !== "string" || !systemPrompt.trim()) {
    return res.status(400).json({ error: "Missing `systemPrompt`." });
  }

  const chatHistory = normalizeMessages(messages);
  if (chatHistory.length === 0) {
    return res.status(400).json({ error: "Missing chat messages." });
  }

  const config = getProviderConfig();
  const client = getClient(config);
  if (!client) {
    return res.status(503).json({
      error: config.missingKeyMessage,
    });
  }

  try {
    const response = await client.responses.create({
      model: config.model,
      reasoning: { effort: config.reasoningEffort },
      instructions: systemPrompt.trim(),
      input: chatHistory,
      max_output_tokens: config.maxOutputTokens,
    });

    const content = response.output_text?.trim();
    if (!content) {
      return res.status(502).json({ error: "The model returned an empty response." });
    }

    return res.json({
      content,
      model: response.model,
    });
  } catch (error) {
    const statusCode = typeof error?.status === "number" ? error.status : 500;
    return res.status(statusCode).json({
      error: getFriendlyError(error),
    });
  }
});

app.post("/api/risk-officer/report", async (req, res) => {
  const { persona } = req.body ?? {};

  if (!persona || typeof persona !== "object") {
    return res.status(400).json({ error: "Missing `persona` payload." });
  }

  try {
    const pdfBuffer = await buildCreditReportPdf(persona);
    const safeAppNo = String(persona.appNo || "gigscore-report").replace(/[^a-zA-Z0-9-_]+/g, "-");

    res
      .status(200)
      .set({
        "Content-Type": "application/pdf",
        "Content-Disposition": `attachment; filename="${safeAppNo}-credit-assessment-report.pdf"`,
        "Content-Length": String(pdfBuffer.length),
      })
      .send(pdfBuffer);
  } catch (error) {
    return res.status(500).json({
      error: getFriendlyError(error),
    });
  }
});

app.post("/api/risk-officer/report-data", async (req, res) => {
  const { persona } = req.body ?? {};

  if (!persona || typeof persona !== "object") {
    return res.status(400).json({ error: "Missing `persona` payload." });
  }

  try {
    const report = buildCreditReport(persona);
    return res.status(200).json(report);
  } catch (error) {
    return res.status(500).json({
      error: getFriendlyError(error),
    });
  }
});

app.post("/api/risk-officer/report-html", async (req, res) => {
  const { persona } = req.body ?? {};

  if (!persona || typeof persona !== "object") {
    return res.status(400).json({ error: "Missing `persona` payload." });
  }

  try {
    const html = buildCreditReportHtml(persona);
    return res
      .status(200)
      .set({ "Content-Type": "text/html; charset=utf-8" })
      .send(html);
  } catch (error) {
    return res.status(500).json({
      error: getFriendlyError(error),
    });
  }
});

app.post("/api/agent5-credit-story/voice", async (req, res) => {
  const { text, language } = req.body ?? {};

  if (typeof text !== "string" || !text.trim()) {
    return res.status(400).json({ error: "Missing `text` payload." });
  }

  try {
    const audio = await buildAgent5VoiceAudio(text.trim(), language === "hi" ? "hi" : "en");

    return res
      .status(200)
      .set({
        "Content-Type": audio.contentType,
        "Content-Length": String(audio.buffer.length),
        "X-Agent5-Voice": audio.voice,
      })
      .send(audio.buffer);
  } catch (error) {
    return res.status(500).json({
      error: getFriendlyError(error),
    });
  }
});

async function start() {
  if (!isProduction) {
    const vite = await createViteServer({
      root: __dirname,
      server: {
        middlewareMode: true,
        host: HOST,
      },
      appType: "custom",
    });

    app.use(vite.middlewares);

    app.use(async (req, res, next) => {
      try {
        const url = req.originalUrl;
        let template = await fs.readFile(path.join(__dirname, "index.html"), "utf-8");
        template = await vite.transformIndexHtml(url, template);
        res.status(200).set({ "Content-Type": "text/html" }).end(template);
      } catch (error) {
        vite.ssrFixStacktrace(error);
        next(error);
      }
    });
  } else {
    const distPath = path.join(__dirname, "dist");
    app.use(express.static(distPath));
    app.use((_req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, HOST, () => {
    const config = getProviderConfig();
    console.log(`GigScore server running at http://${HOST}:${PORT}`);
    console.log(`Risk Officer provider: ${config.provider} · model: ${config.model}`);
    if (!config.apiKey) {
      console.log(config.missingKeyMessage);
    }
  });
}

start();
