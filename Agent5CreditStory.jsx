import { useEffect, useMemo, useRef, useState } from "react";

const NAVY = "#083B59";
const NAVY_DARK = "#062E45";
const NAVY_SOFT = "#0B4F74";
const BLUE = "#00AEEF";
const BLUE_BG = "#D9F3FB";
const PANEL = "#FFFFFF";
const PANEL_ALT = "#F4FAFD";
const PANEL_LINE = "#BFD7E4";
const PAGE_BG = "#EAF4F8";
const TEXT = "#0A3046";
const TEXT_MUTED = "#58798D";
const TEXT_FAINT = "#88A8BA";
const GREEN = "#187E70";
const GREEN_BG = "#D9F1EC";
const AMBER = "#B6781D";
const AMBER_BG = "#FFF1D8";
const RED = "#C65B56";
const RED_BG = "#FBE5E2";

function fmt(n) {
  return Number(n).toLocaleString("en-IN");
}

function decisionType(label = "") {
  const normalized = label.toLowerCase();
  if (normalized.includes("conditional")) return "conditional";
  if (normalized.includes("approved")) return "approved";
  return "declined";
}

function languageLabel(language) {
  return language === "hi" ? "Hindi" : "English";
}

function buildProcessSteps(persona, language) {
  const positiveSignals = persona.signals.pos.slice(0, 2).map((signal) => signal.name).join(" and ");
  const riskSignals = persona.signals.neg.slice(0, 2).map((signal) => signal.name).join(" and ");
  const selectedLanguage = languageLabel(language);

  return [
    {
      title: "Customer Call Trigger",
      detail: `The IVR package is prepared for ${persona.name} as a borrower-facing explanation call with fixed customer disclosures.`,
    },
    {
      title: "Language Prompt",
      detail: `The IVR opener asks “Would you prefer Hindi or English?” and the call continues in ${selectedLanguage}, in line with the borrower's understood language requirement.`,
    },
    {
      title: "Decision Intake",
      detail: `GigScore loads ${persona.appNo}, score ${persona.scores.final}, default probability ${persona.decision.prob}%, and the borrower decision outcome.`,
    },
    {
      title: "Reason Pack",
      detail: `The system bundles the key supporting signals ${positiveSignals} together with the main caution signals ${riskSignals} for customer explanation.`,
    },
    {
      title: "Fair Practices Script",
      detail: "Agent 5 converts the decision into a plain-language borrower script covering reasons, key terms where applicable, and next steps.",
    },
    {
      title: "Customer Rights Check",
      detail: "The call adds written follow-up, agreement disclosure, and grievance guidance so the IVR stays aligned with RBI Fair Practices expectations.",
    },
  ];
}

function buildScript(persona, language) {
  const status = decisionType(persona.decision.label);
  const positive1 = persona.signals.pos[0];
  const positive2 = persona.signals.pos[1];
  const risk1 = persona.signals.neg[0];
  const risk2 = persona.signals.neg[1];

  if (language === "hi") {
    const opening = `नमस्ते ${persona.name}। यह कॉल आपके ऋण आवेदन ${persona.appNo} के बारे में है। क्या आप हिन्दी पसंद करेंगे या अंग्रेज़ी? इस प्रीव्यू के लिए हिन्दी चुनी गई है।`;

    const decisionSummary =
      status === "approved"
        ? `आपके आवेदन का निष्पक्ष आकलन करने के बाद इसे स्वीकृत किया गया है। आपका GigScore ${persona.scores.final} है और default probability ${persona.decision.prob}% है। यह प्रोफाइल ${persona.decision.tier} जोखिम श्रेणी में स्वीकार्य मानी गई है।`
        : status === "conditional"
          ? `आपके आवेदन को सशर्त स्वीकृति दी गई है। आपका GigScore ${persona.scores.final} है और default probability ${persona.decision.prob}% है। इसका अर्थ है कि आपका प्रोफाइल सेवा योग्य है, लेकिन कुछ जोखिम संकेतों के कारण अतिरिक्त सावधानी रखी जाएगी।`
          : `आपके आवेदन को इस समय स्वीकृत नहीं किया जा सकता क्योंकि वर्तमान जोखिम प्रोफाइल नीति सीमा से ऊपर है। इस कॉल का उद्देश्य निर्णय के मुख्य कारण साफ भाषा में बताना है।`;

    const reasonCodes = `आपके पक्ष में मुख्य संकेत ${positive1.name.toLowerCase()} (${positive1.val}) और ${positive2.name.toLowerCase()} (${positive2.val}) हैं। मुख्य सावधानी बिंदु ${risk1.name.toLowerCase()} (${risk1.val}) और ${risk2.name.toLowerCase()} (${risk2.val}) हैं। आय में उतार-चढ़ाव को गिग काम की सामान्य विशेषता माना गया है, केवल कमी नहीं।`;

    const keyTerms =
      status === "declined"
        ? "अस्वीकृति की स्थिति में लिखित रूप में मुख्य कारण साझा किए जाएंगे। आप नकदी संतुलन, भुगतान अनुशासन और व्यवहार संकेतों में सुधार के बाद पुनर्मूल्यांकन का अनुरोध कर सकते हैं।"
        : `यदि आप आगे बढ़ते हैं, तो प्रस्तावित शर्तें हैं: Rs ${fmt(persona.loan.amount)} की राशि, ${persona.loan.rate}% वार्षिक ब्याज, ${persona.loan.tenure} महीनों की अवधि, Rs ${fmt(persona.loan.emi)} की EMI, और Rs ${fmt(persona.loan.fee)} की processing fee। FOIR ${persona.loan.foir}% है।`;

    const rightsAndSupport =
      status === "declined"
        ? "RBI Fair Practices के अनुरूप, इस निर्णय के मुख्य कारण आपको लिखित रूप में दिए जाने चाहिए। यदि आपको स्पष्टीकरण चाहिए या शिकायत दर्ज करनी है, तो कृपया अपने ऋणदाता के grievance redressal channel से संपर्क करें।"
        : "RBI Fair Practices के अनुरूप, आपको ऋण की शर्तें, annualised rate, charges, और agreement की प्रति लिखित रूप में उपलब्ध कराई जानी चाहिए। यदि कोई प्रश्न या शिकायत हो, तो कृपया अपने ऋणदाता के grievance redressal channel का उपयोग करें।";

    return [
      { label: "Language Prompt", text: opening },
      { label: "Decision Summary", text: decisionSummary },
      { label: "Reason Codes", text: reasonCodes },
      { label: status === "declined" ? "Next Steps" : "Key Terms", text: keyTerms },
      { label: "Borrower Rights", text: rightsAndSupport },
    ];
  }

  const opening = `Hello ${persona.name}. This call is about your loan application ${persona.appNo}. Would you prefer Hindi or English? English has been selected for this preview.`;

  const decisionSummary =
    status === "approved"
      ? `After a fair assessment of your application, your loan is approved. Your GigScore is ${persona.scores.final} and your default probability is ${persona.decision.prob}%. This profile falls within an acceptable ${persona.decision.tier} risk band.`
      : status === "conditional"
        ? `Your loan is conditionally approved. Your GigScore is ${persona.scores.final} and your default probability is ${persona.decision.prob}%. This means your profile is serviceable, but some risk signals require extra caution and clear conditions before disbursal.`
        : `Your loan application cannot be approved at this stage because the current risk profile is outside policy tolerance. This call explains the main reasons in plain language.`;

  const reasonCodes = `The strongest supporting factors are ${positive1.name.toLowerCase()} (${positive1.val}) and ${positive2.name.toLowerCase()} (${positive2.val}). The main caution points are ${risk1.name.toLowerCase()} (${risk1.val}) and ${risk2.name.toLowerCase()} (${risk2.val}). Income variability has been treated as a normal feature of gig work, not as a flaw by itself.`;

  const keyTerms =
    status === "declined"
      ? "If your application is declined, the main reasons should also be shared with you in writing. You may request a fresh review after improving cash-flow balance, payment discipline, and other behavioural signals."
      : `If you proceed, the proposed terms are Rs ${fmt(persona.loan.amount)} at an annual interest rate of ${persona.loan.rate}% for ${persona.loan.tenure} months, with an EMI of Rs ${fmt(persona.loan.emi)} and a processing fee of Rs ${fmt(persona.loan.fee)}. FOIR is ${persona.loan.foir}%.`;

  const rightsAndSupport =
    status === "declined"
      ? "Under RBI Fair Practices expectations, the main reason for rejection should be communicated to you in writing within the stipulated time. If you need clarification or want to raise a grievance, please use your lender's grievance redressal channel."
      : "Under RBI Fair Practices expectations, you should receive the loan terms, annualised rate, charges, and loan agreement details in writing in a language you understand. If you have questions or want to raise a grievance, please use your lender's grievance redressal channel before accepting the offer.";

  return [
    { label: "Language Prompt", text: opening },
    { label: "Decision Summary", text: decisionSummary },
    { label: "Reason Codes", text: reasonCodes },
    { label: status === "declined" ? "Next Steps" : "Key Terms", text: keyTerms },
    { label: "Borrower Rights", text: rightsAndSupport },
  ];
}

function WaveBars({ active }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 26 }}>
      {Array.from({ length: 12 }).map((_, index) => (
        <span
          key={index}
          style={{
            width: 4,
            height: active ? 10 + ((index * 7) % 14) : 6,
            borderRadius: 999,
            background: active ? `linear-gradient(180deg, ${BLUE} 0%, ${NAVY} 100%)` : PANEL_LINE,
            animation: active ? `agent5-wave 1.1s ${index * 0.08}s infinite ease-in-out alternate` : "none",
          }}
        />
      ))}
    </div>
  );
}

function pickBrowserVoice(language) {
  if (typeof window === "undefined" || !window.speechSynthesis) return null;

  const voices = window.speechSynthesis.getVoices();
  const exactLanguage = language === "hi" ? "hi-IN" : "en-IN";
  const languagePrefix = language === "hi" ? "hi" : "en";
  const preferredNames = language === "hi"
    ? ["Lekha", "Google", "Microsoft", "Natural", "Enhanced"]
    : ["Rishi", "Google", "Microsoft", "Natural", "Samantha", "Daniel", "Enhanced"];

  for (const preferredName of preferredNames) {
    const match = voices.find((voice) =>
      voice.lang === exactLanguage && voice.name.toLowerCase().includes(preferredName.toLowerCase()),
    );
    if (match) return match;
  }

  return (
    voices.find((voice) => voice.lang === exactLanguage) ||
    voices.find((voice) => voice.lang.startsWith(languagePrefix)) ||
    null
  );
}

export default function Agent5CreditStory({ persona }) {
  const [language, setLanguage] = useState("en");
  const [processing, setProcessing] = useState(false);
  const [activeStep, setActiveStep] = useState(-1);
  const [completedSteps, setCompletedSteps] = useState([]);
  const [ready, setReady] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [voiceSource, setVoiceSource] = useState("macOS voice");
  const [voiceError, setVoiceError] = useState("");

  const timersRef = useRef([]);
  const utteranceRef = useRef(null);
  const audioRef = useRef(null);
  const audioUrlRef = useRef("");

  const steps = useMemo(() => buildProcessSteps(persona, language), [persona, language]);
  const scriptSections = useMemo(() => buildScript(persona, language), [persona, language]);
  const progress = completedSteps.length / steps.length;

  const clearTimers = () => {
    timersRef.current.forEach((timer) => clearTimeout(timer));
    timersRef.current = [];
  };

  const clearAudioAsset = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.onplay = null;
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current = null;
    }

    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = "";
    }
  };

  const stopAudio = () => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    utteranceRef.current = null;
    clearAudioAsset();
    setIsPlaying(false);
  };

  useEffect(() => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.getVoices();
    }

    return () => {
      clearTimers();
      stopAudio();
    };
  }, []);

  useEffect(() => {
    clearTimers();
    stopAudio();
    setProcessing(false);
    setActiveStep(-1);
    setCompletedSteps([]);
    setReady(false);
    setVoiceError("");
    setVoiceSource("macOS voice");
  }, [persona.appNo]);

  useEffect(() => {
    stopAudio();
    setVoiceError("");
  }, [language]);

  const runIvrFlow = () => {
    clearTimers();
    stopAudio();
    setProcessing(true);
    setReady(false);
    setCompletedSteps([]);
    setActiveStep(0);
    setVoiceError("");

    steps.forEach((_, index) => {
      timersRef.current.push(
        setTimeout(() => {
          setActiveStep(index);
        }, index * 800),
      );

      timersRef.current.push(
        setTimeout(() => {
          setCompletedSteps((prev) => (prev.includes(index) ? prev : [...prev, index]));

          if (index === steps.length - 1) {
            setProcessing(false);
            setActiveStep(-1);
            setReady(true);
          }
        }, index * 800 + 500),
      );
    });
  };

  const playBrowserFallback = (text) => {
    if (typeof window === "undefined" || !window.speechSynthesis || typeof SpeechSynthesisUtterance === "undefined") {
      throw new Error("Speech playback is not available in this browser.");
    }

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    const voice = pickBrowserVoice(language);
    utterance.lang = language === "hi" ? "hi-IN" : "en-IN";
    utterance.rate = language === "hi" ? 0.94 : 0.98;
    utterance.pitch = 1;

    if (voice) {
      utterance.voice = voice;
      setVoiceSource(`Browser fallback · ${voice.name}`);
    } else {
      setVoiceSource("Browser fallback voice");
    }

    utterance.onstart = () => setIsPlaying(true);
    utterance.onend = () => setIsPlaying(false);
    utterance.onerror = () => setIsPlaying(false);
    utteranceRef.current = utterance;
    window.speechSynthesis.speak(utterance);
  };

  const playAudioPreview = async () => {
    if (!ready) return;

    const text = scriptSections.map((section) => section.text).join(" ");
    stopAudio();
    setVoiceError("");

    try {
      const response = await fetch("/api/agent5-credit-story/voice", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || "Local IVR voice generation failed.");
      }

      const blob = await response.blob();
      const voiceHeader = response.headers.get("X-Agent5-Voice");
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioUrlRef.current = url;
      audioRef.current = audio;

      audio.onplay = () => {
        setIsPlaying(true);
        setVoiceSource(voiceHeader ? `macOS voice · ${voiceHeader}` : "macOS voice");
      };
      audio.onended = () => {
        setIsPlaying(false);
        clearAudioAsset();
      };
      audio.onerror = () => {
        setIsPlaying(false);
        clearAudioAsset();
        setVoiceError("Local voice playback failed. Falling back to browser speech.");
        try {
          playBrowserFallback(text);
        } catch (error) {
          setVoiceError(error?.message || "Voice playback is not available.");
        }
      };

      await audio.play();
    } catch (error) {
      setVoiceError("Local IVR voice could not be generated. Using browser fallback voice instead.");

      try {
        playBrowserFallback(text);
      } catch (fallbackError) {
        setVoiceError(fallbackError?.message || error?.message || "Voice playback is not available.");
      }
    }
  };

  return (
    <div style={{
      background: PANEL,
      borderRadius: 20,
      border: `1px solid ${PANEL_LINE}`,
      boxShadow: "0 20px 50px rgba(6, 46, 69, 0.08)",
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
      minHeight: 0,
    }}>
      <div style={{
        padding: "16px 18px",
        borderBottom: `1px solid ${PANEL_LINE}`,
        background: `linear-gradient(135deg, ${NAVY_DARK} 0%, ${NAVY} 68%, ${NAVY_SOFT} 100%)`,
        color: "#F6FBFE",
      }}>
        <div style={{ fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase", color: "#A5C8D8", marginBottom: 8 }}>
          Agent 5
        </div>
        <div style={{ fontSize: 20, fontWeight: 600, lineHeight: 1.2, marginBottom: 6 }}>
          IVR Explainability Bot
        </div>
        <div style={{ fontSize: 12, lineHeight: 1.55, color: "#D4ECF6" }}>
          Borrower-facing IVR preview with language choice, plain-language reasons, key terms, and natural audio generated from your Mac&apos;s Indian voices.
        </div>
      </div>

      <div style={{ padding: "16px 18px", overflowY: "auto" }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
          {[
            "Borrower-facing IVR",
            "Hindi and English",
            "Local natural voice",
          ].map((label) => (
            <span key={label} style={{
              background: BLUE_BG,
              color: NAVY,
              border: `1px solid ${PANEL_LINE}`,
              borderRadius: 999,
              padding: "5px 10px",
              fontSize: 11,
              fontWeight: 600,
            }}>
              {label}
            </span>
          ))}
        </div>

        <div style={{
          background: PANEL_ALT,
          border: `1px solid ${PANEL_LINE}`,
          borderRadius: 16,
          padding: "14px 14px 16px",
          marginBottom: 16,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", marginBottom: 12 }}>
            <div>
              <div style={{ fontSize: 11, color: TEXT_FAINT, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
                Call Package
              </div>
              <div style={{ fontSize: 14, color: TEXT, fontWeight: 600 }}>
                {persona.name} · {persona.appNo} · Customer Explanation
              </div>
            </div>
            <button onClick={runIvrFlow} disabled={processing} style={{
              background: processing ? TEXT_FAINT : NAVY,
              color: "#fff",
              border: "none",
              borderRadius: 10,
              padding: "10px 14px",
              fontSize: 12,
              fontWeight: 600,
              cursor: processing ? "not-allowed" : "pointer",
              whiteSpace: "nowrap",
            }}>
              {processing ? "Processing Customer IVR..." : "Process Customer IVR"}
            </button>
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 10, color: TEXT_FAINT, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>
              Preferred Language
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {[
                { id: "en", label: "English", sub: "Start in English" },
                { id: "hi", label: "हिन्दी", sub: "हिन्दी में जारी रखें" },
              ].map((option) => (
                <button
                  key={option.id}
                  onClick={() => setLanguage(option.id)}
                  style={{
                    background: language === option.id ? BLUE_BG : PANEL,
                    border: `1px solid ${language === option.id ? BLUE : PANEL_LINE}`,
                    borderRadius: 12,
                    padding: "12px 12px",
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  <div style={{ fontSize: 13, color: TEXT, fontWeight: 600, marginBottom: 4 }}>
                    {option.label}
                  </div>
                  <div style={{ fontSize: 11, color: TEXT_MUTED }}>
                    {option.sub}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div style={{ height: 8, borderRadius: 999, background: PAGE_BG, overflow: "hidden", marginBottom: 8 }}>
            <div style={{
              width: `${Math.max(progress * 100, processing ? 10 : 0)}%`,
              height: "100%",
              background: `linear-gradient(90deg, ${BLUE} 0%, ${NAVY} 100%)`,
              transition: "width 0.35s ease",
            }} />
          </div>
              <div style={{ fontSize: 11, color: TEXT_MUTED, display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span>{ready ? `Customer IVR package ready in ${languageLabel(language)}` : processing ? "Running the borrower call flow" : "Launch the flow to build the borrower IVR package"}</span>
            <span>{completedSteps.length}/{steps.length}</span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
          {steps.map((step, index) => {
            const isDone = completedSteps.includes(index);
            const isActive = activeStep === index && processing;
            return (
              <div key={step.title} style={{
                border: `1px solid ${isActive ? BLUE : isDone ? "#9FDCCF" : PANEL_LINE}`,
                background: isActive ? BLUE_BG : isDone ? GREEN_BG : PANEL_ALT,
                borderRadius: 16,
                padding: "12px 13px",
                transition: "background 0.2s ease, border-color 0.2s ease",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                  <div style={{
                    width: 24,
                    height: 24,
                    borderRadius: "50%",
                    background: isDone ? GREEN : isActive ? NAVY : PANEL,
                    color: isDone || isActive ? "#fff" : TEXT_FAINT,
                    border: `1px solid ${isDone ? GREEN : isActive ? NAVY : PANEL_LINE}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 11,
                    fontWeight: 700,
                    flexShrink: 0,
                  }}>
                    {isDone ? "OK" : index + 1}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: TEXT }}>{step.title}</div>
                    <div style={{ fontSize: 11, color: TEXT_MUTED, lineHeight: 1.5 }}>{step.detail}</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div style={{
          background: PANEL_ALT,
          border: `1px solid ${PANEL_LINE}`,
          borderRadius: 16,
          padding: "14px 14px 16px",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", marginBottom: 12 }}>
            <div>
              <div style={{ fontSize: 11, color: TEXT_FAINT, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
                Audio Bot
              </div>
              <div style={{ fontSize: 14, color: TEXT, fontWeight: 600 }}>
                Borrower IVR Preview
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <WaveBars active={isPlaying} />
              {!isPlaying ? (
                <button onClick={playAudioPreview} disabled={!ready} style={{
                  background: ready ? NAVY_SOFT : TEXT_FAINT,
                  color: "#fff",
                  border: "none",
                  borderRadius: 10,
                  padding: "9px 12px",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: ready ? "pointer" : "not-allowed",
                }}>
                  Start Customer Call Preview
                </button>
              ) : (
                <button onClick={stopAudio} style={{
                  background: AMBER,
                  color: "#fff",
                  border: "none",
                  borderRadius: 10,
                  padding: "9px 12px",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                }}>
                  Stop Audio
                </button>
              )}
            </div>
          </div>

          <div style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 12,
            alignItems: "center",
            background: PANEL,
            border: `1px solid ${PANEL_LINE}`,
            borderRadius: 12,
            padding: "10px 12px",
            marginBottom: 12,
          }}>
            <div>
              <div style={{ fontSize: 10, color: TEXT_FAINT, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 3 }}>
                Voice Route
              </div>
              <div style={{ fontSize: 12, color: TEXT, fontWeight: 600 }}>
                {voiceSource}
              </div>
            </div>
            <div style={{ fontSize: 11, color: TEXT_MUTED }}>
              {language === "hi" ? "हिन्दी" : "English"} · {language === "hi" ? "hi-IN" : "en-IN"}
            </div>
          </div>

          {voiceError && (
            <div style={{
              background: RED_BG,
              border: `1px solid #F0B0AB`,
              color: RED,
              borderRadius: 12,
              padding: "9px 11px",
              fontSize: 11,
              lineHeight: 1.5,
              marginBottom: 12,
            }}>
              {voiceError}
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {scriptSections.map((section) => (
              <div key={section.label} style={{
                background: PANEL,
                border: `1px solid ${PANEL_LINE}`,
                borderRadius: 14,
                padding: "12px 13px",
                opacity: ready ? 1 : 0.6,
              }}>
                <div style={{ fontSize: 10, color: TEXT_FAINT, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 5 }}>
                  {section.label}
                </div>
                <div style={{ fontSize: 12.5, color: TEXT, lineHeight: 1.6 }}>
                  {section.text}
                </div>
              </div>
            ))}
          </div>

          <div style={{
            marginTop: 12,
            background: ready ? AMBER_BG : PAGE_BG,
            border: `1px solid ${ready ? "#F1D08C" : PANEL_LINE}`,
            color: ready ? AMBER : TEXT_MUTED,
            borderRadius: 12,
            padding: "10px 12px",
            fontSize: 11,
            lineHeight: 1.55,
          }}>
            {ready
              ? "The preview now behaves like a customer explanation call: language choice first, then decision reasons, key terms where applicable, and borrower rights."
              : "Run the IVR flow once, choose the language, and then start the customer call preview."}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes agent5-wave {
          0% { transform: scaleY(0.45); opacity: 0.65; }
          100% { transform: scaleY(1.2); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
