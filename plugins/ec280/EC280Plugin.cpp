#include "DistrhoPlugin.hpp"

#include <cmath>
#include <cstring>
#include <vector>

START_NAMESPACE_DISTRHO

// ---------------------------------------------------------------------------
// EC 280 model. A virtual bucket-brigade line is clocked by its own clock
// (about 6.8-51 kHz), independent of the host rate: input is sampled at each
// clock tick and the taps are read back at the host rate. Aliasing, the dark
// top end and the pitch-warp when Speed moves all come from that, as on the
// hardware. All memory is allocated in the constructor.

static const double kMaxSampleRate = 96000.0;
static const float  kAntiDenormal  = 1e-18f;
static const float  kPi            = 3.14159265f;

// Line: 16 chips x 512 stages = 8192 stages. Two stages per clock period, so
// 4096 buckets. Buffer is one power of two bigger so the longest tap never
// reads the slot being written.
static const uint32_t kLineSize  = 8192;
static const uint32_t kLineMask  = kLineSize - 1;
static const uint32_t kPairSlots = 512;       // one chip pair = 1024 stages

// Clock range: Vintage 40-300 ms over 2048 buckets.
static const float kMinDelay = 0.040f;
static const float kMaxDelay = 0.300f;

// Resistor matrix, kOhm, from the schematic (2-1606 b). Index = tap 1..4
// (tap 1 is shortest). 0 = not connected.
static const float kLoadK = 47.0f;            // bus load (pot + next stage), guess
static const float kEchoWet[4]    = { 0.0f, 0.0f, 0.0f, 330.0f };
static const float kEchoFbK       = 140.0f;   // 130k per button + shared 10k
static const int   kEchoTap[4]    = { 3, 2, 1, 0 };   // E1..E4 -> tap index
static const float kHallWet[4][4] = {
    { 403.0f, 452.0f, 506.0f, 566.0f },       // H1
    { 452.0f, 570.0f, 719.0f, 902.0f },       // H2
    { 360.0f, 360.0f,   0.0f,   0.0f },       // H3
    { 360.0f, 360.0f, 360.0f,   0.0f },       // H4
};
static const float kHallFb[4][4] = {
    { 0.0f,   0.0f,   0.0f, 140.0f },         // H1: tap 4
    { 0.0f,   0.0f,   0.0f, 190.0f },         // H2: tap 4
    { 0.0f, 140.0f,   0.0f,   0.0f },         // H3: tap 2 (read uncertain)
    { 140.0f, 0.0f,   0.0f,   0.0f },         // H4: tap 1 (read uncertain)
};

// Normalisation: Echo mode's single wet tap comes out at unity, and a single
// feedback tap gives the loop gain set by Duration.
static const float kWetNorm = 1.0f + 330.0f / kLoadK;
static const float kFbNorm  = 1.0f + kEchoFbK / kLoadK;

static inline float onePoleCoef(float hz, float sr)
{
    return 1.0f - std::exp(-2.0f * kPi * hz / sr);
}

// Rational tanh approximation (accurate for |x| < 3).
static inline float softClip(float x)
{
    if (x >  3.0f) return  1.0f;
    if (x < -3.0f) return -1.0f;
    const float x2 = x * x;
    return x * (27.0f + x2) / (27.0f + 9.0f * x2);
}

// 2-pole low-pass (RBJ), standing in for a unity-gain Sallen-Key stage.
struct Biquad
{
    float b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0;
    float z1 = 0, z2 = 0;

    void lowpass(float hz, float q, float sr)
    {
        if (hz > 0.45f * sr) hz = 0.45f * sr;
        const float w  = 2.0f * kPi * hz / sr;
        const float cw = std::cos(w), al = std::sin(w) / (2.0f * q);
        const float a0 = 1.0f + al;
        b0 = (1.0f - cw) * 0.5f / a0;
        b1 = (1.0f - cw) / a0;
        b2 = b0;
        a1 = -2.0f * cw / a0;
        a2 = (1.0f - al) / a0;
    }
    void clear() { z1 = z2 = 0.0f; }
    inline float process(float x)
    {
        const float y = b0 * x + z1;
        z1 = b1 * x - a1 * y + z2;
        z2 = b2 * x - a2 * y;
        return y;
    }
};

// ---------------------------------------------------------------------------

class EC280Plugin : public Plugin
{
public:
    EC280Plugin()
        : Plugin(kParameterCount, 0, 0)
    {
        fParams[kVolume]   = 5.0f;
        fParams[kSpeed]    = 5.0f;
        fParams[kDuration] = 4.0f;
        fParams[kReturn]   = 6.0f;
        fParams[kChorus]   = 2.0f;
        fParams[kMode]     = 0.0f;
        fParams[kEchoTaps] = 1.0f;
        fParams[kHallTaps] = 1.0f;
        fParams[kRange]    = 0.0f;
        fParams[kTails]    = 1.0f;
        fParams[kBypass]   = 0.0f;

        fLine.assign(kLineSize, 0.0f);
        activate();
    }

protected:
    const char* getLabel()       const override { return "EC280"; }
    const char* getDescription() const override { return "Dark bucket-brigade echo and reverb with random-drift chorus, modelled on the 1977 Dynacord EC 280."; }
    const char* getMaker()       const override { return "New Horizon Electronics"; }
    const char* getHomePage()    const override { return "https://github.com/Kiwooky/NHE-EC280"; }
    const char* getLicense()     const override { return "MIT"; }
    uint32_t    getVersion()     const override { return d_version(1, 0, 0); }
    int64_t     getUniqueId()    const override { return d_cconst('E', 'c', '2', '8'); }

    void initParameter(uint32_t index, Parameter& p) override
    {
        p.hints = kParameterIsAutomatable;
        p.ranges.min = 0.0f;
        p.ranges.max = 10.0f;

        switch (index) {
        case kVolume:
            p.name = "Volume"; p.symbol = "volume"; p.ranges.def = 5.0f;
            break;
        case kSpeed:
            p.name = "Speed"; p.symbol = "speed"; p.ranges.def = 5.0f;
            break;
        case kDuration:
            p.name = "Duration"; p.symbol = "duration"; p.ranges.def = 4.0f;
            break;
        case kReturn:
            p.name = "Return"; p.symbol = "return_level"; p.ranges.def = 6.0f;
            break;
        case kChorus:
            p.name = "Chorus"; p.symbol = "chorus"; p.ranges.def = 2.0f;
            break;
        case kMode: {
            p.hints |= kParameterIsInteger;
            p.name = "Echo / Reverb"; p.symbol = "mode";
            p.ranges.max = 1.0f; p.ranges.def = 0.0f;
            ParameterEnumerationValue* const v = new ParameterEnumerationValue[2];
            v[0].label = "Echo"; v[0].value = 0.0f;
            v[1].label = "Reverb"; v[1].value = 1.0f;
            p.enumValues.count = 2; p.enumValues.restrictedMode = true; p.enumValues.values = v;
            break;
        }
        case kEchoTaps:
            p.name = "Echo buttons"; p.symbol = "echo_taps";
            initBank(p, "E");
            break;
        case kHallTaps:
            p.name = "Reverb buttons"; p.symbol = "hall_taps";
            initBank(p, "R");
            break;
        case kRange: {
            p.hints |= kParameterIsInteger;
            p.name = "Range"; p.symbol = "range";
            p.ranges.max = 1.0f; p.ranges.def = 0.0f;
            ParameterEnumerationValue* const v = new ParameterEnumerationValue[2];
            v[0].label = "Vintage"; v[0].value = 0.0f;
            v[1].label = "Extended"; v[1].value = 1.0f;
            p.enumValues.count = 2; p.enumValues.restrictedMode = true; p.enumValues.values = v;
            break;
        }
        case kTails:
            p.hints |= kParameterIsInteger | kParameterIsBoolean;
            p.name = "Tails"; p.symbol = "tails";
            p.ranges.max = 1.0f; p.ranges.def = 1.0f;
            break;
        case kBypass:
            p.initDesignation(kParameterDesignationBypass);
            break;
        }
    }

    // Button bank: a bitmask 1-15 (button 1 = bit 0), each value labelled.
    static void initBank(Parameter& p, const char* letter)
    {
        p.hints |= kParameterIsInteger;
        p.ranges.min = 1.0f; p.ranges.max = 15.0f; p.ranges.def = 1.0f;
        ParameterEnumerationValue* const v = new ParameterEnumerationValue[15];
        for (int m = 1; m <= 15; ++m) {
            String label;
            if (m == 15) {
                label = "All";
            } else {
                for (int b = 0; b < 4; ++b) {
                    if (m & (1 << b)) {
                        if (label.isNotEmpty()) label += "+";
                        label += letter;
                        label += String(b + 1);
                    }
                }
            }
            v[m - 1].label = label;
            v[m - 1].value = (float)m;
        }
        p.enumValues.count = 15; p.enumValues.restrictedMode = true; p.enumValues.values = v;
    }

    float getParameterValue(uint32_t index) const override
    {
        return (index < kParameterCount) ? fParams[index] : 0.0f;
    }

    void setParameterValue(uint32_t index, float value) override
    {
        if (index < kParameterCount) fParams[index] = value;
    }

    void activate() override
    {
        fSr = (float)getSampleRate();
        if (fSr <= 0.0f) fSr = 48000.0f;
        if (fSr > (float)kMaxSampleRate) fSr = (float)kMaxSampleRate;

        // Input (anti-alias) and output (reconstruction) filters: two
        // Sallen-Key stages each, about 4.0 and 3.3 kHz, Q about 0.9.
        fIn1.lowpass(4000.0f, 0.9f, fSr);  fIn2.lowpass(3300.0f, 0.9f, fSr);
        fOut1.lowpass(4000.0f, 0.9f, fSr); fOut2.lowpass(3300.0f, 0.9f, fSr);

        fPairCoef  = onePoleCoef(12000.0f, fSr);   // per chip pair loss
        fDcCoef    = onePoleCoef(20.0f, fSr);      // coupling caps in the loop
        fGlideCoef = 1.0f - std::exp(-1.0f / (0.027f * fSr));   // R790 x C629
        fFadeCoef  = 1.0f - std::exp(-1.0f / (0.010f * fSr));
        fNoiseLp   = onePoleCoef(1.6f, fSr);
        fNoiseHp   = onePoleCoef(0.5f, fSr);
        fNoiseNorm = std::sqrt(2.0f / fNoiseLp);   // white noise -> unit variance

        clearState();
        fCleared = false;
        fClock = speedToClock(fParams[kSpeed]);
        fFresh = true;   // first run() snaps the clock instead of gliding

        const bool bypassed = fParams[kBypass] > 0.5f;
        fInGain  = bypassed ? 0.0f : 1.0f;
        fWetGain = (bypassed && fParams[kTails] < 0.5f) ? 0.0f : 1.0f;
        fDryGain = bypassed ? 1.0f : volumeGain(fParams[kVolume]);
    }

    void clearState()
    {
        std::memset(fLine.data(), 0, kLineSize * sizeof(float));
        fWrite = 0;
        fPhase = 0.0f;
        fPrevIn = 0.0f;
        fDurBus = 0.0f;
        fDcX = fDcY = 0.0f;
        std::memset(fTapPrev, 0, sizeof(fTapPrev));
        std::memset(fTapCur, 0, sizeof(fTapCur));
        std::memset(fPairZ, 0, sizeof(fPairZ));
        fIn1.clear(); fIn2.clear(); fOut1.clear(); fOut2.clear();
        fNoiseZ = fNoiseH = 0.0f;
    }

    static float speedToClock(float speed)
    {
        // log pot: delay = 300 ms x (40/300)^(speed/10), over 2048 buckets
        const float d = kMaxDelay * std::pow(kMinDelay / kMaxDelay, speed / 10.0f);
        return 2048.0f / d;
    }
    static float volumeGain(float v) { const float g = v / 5.0f; return g * g; }   // unity at 5, +12 dB at 10

    inline float rnd()   // xorshift32, -1..1
    {
        fSeed ^= fSeed << 13; fSeed ^= fSeed >> 17; fSeed ^= fSeed << 5;
        return (float)(int32_t)fSeed * (1.0f / 2147483648.0f);
    }

    // Asymmetric soft clip standing in for the bucket headroom (~ -6 dBFS).
    static inline float bucketClip(float x)
    {
        const float h = 0.5f, b = 0.15f;
        return h * (softClip(x / h + b) - softClip(b));
    }

    void run(const float** inputs, float** outputs, uint32_t frames) override
    {
        const float* in     = inputs[0];
        float*       outMix = outputs[0];
        float*       outEch = outputs[1];

        const float sr = fSr;

        // --- controls ---------------------------------------------------
        const float vol      = volumeGain(fParams[kVolume]);
        const float clkTgt   = speedToClock(fParams[kSpeed]);
        const float loopGain = 1.25f * fParams[kDuration] / 10.0f;    // 1.0 at 8
        const float r        = fParams[kReturn] / 10.0f;
        const float retGain  = r * r * kWetNorm;
        const float chorusHz = 1000.0f * fParams[kChorus] / 10.0f;
        const bool  hall     = fParams[kMode] > 0.5f;
        const bool  extended = fParams[kRange] > 0.5f;

        int echoMask = (int)(fParams[kEchoTaps] + 0.5f);
        int hallMask = (int)(fParams[kHallTaps] + 0.5f);
        if (echoMask < 1) echoMask = 1; else if (echoMask > 15) echoMask = 15;
        if (hallMask < 1) hallMask = 1; else if (hallMask > 15) hallMask = 15;

        // --- resistor matrix -> tap weights for the two passive buses ----
        float gWet[4] = { 0, 0, 0, 0 }, gFb[4] = { 0, 0, 0, 0 };
        if (hall) {
            for (int b = 0; b < 4; ++b) {
                if (!(hallMask & (1 << b))) continue;
                for (int t = 0; t < 4; ++t) {
                    if (kHallWet[b][t] > 0.0f) gWet[t] += 1.0f / kHallWet[b][t];
                    if (kHallFb[b][t]  > 0.0f) gFb[t]  += 1.0f / kHallFb[b][t];
                }
            }
        } else {
            for (int t = 0; t < 4; ++t)
                if (kEchoWet[t] > 0.0f) gWet[t] += 1.0f / kEchoWet[t];
            for (int b = 0; b < 4; ++b)
                if (echoMask & (1 << b)) gFb[kEchoTap[b]] += 1.0f / kEchoFbK;
        }
        float sumW = 1.0f / kLoadK, sumF = 1.0f / kLoadK;
        for (int t = 0; t < 4; ++t) { sumW += gWet[t]; sumF += gFb[t]; }
        float wWet[4], wFb[4];
        for (int t = 0; t < 4; ++t) {
            wWet[t] = gWet[t] / sumW;
            wFb[t]  = gFb[t]  / sumF * kFbNorm * loopGain;
        }

        // Range: the taps sit after chip pairs 1-4 (Vintage) or 2, 4, 6, 8
        // (Extended). Switching just moves the read points, like hardware.
        const uint32_t pairsPerTap = extended ? 2 : 1;
        uint32_t tapSlots[4];
        for (int t = 0; t < 4; ++t) tapSlots[t] = kPairSlots * pairsPerTap * (uint32_t)(t + 1);

        // --- bypass / tails ------------------------------------------------
        const bool bypassed = fParams[kBypass] > 0.5f;
        const bool tails    = fParams[kTails]  > 0.5f;
        const float inTarget  = bypassed ? 0.0f : 1.0f;
        const float wetTarget = (bypassed && !tails) ? 0.0f : 1.0f;
        const float dryTarget = bypassed ? 1.0f : vol;

        if (bypassed && !tails && fWetGain < 1e-4f && !fCleared) {
            clearState();
            fCleared = true;
        }
        if (!bypassed) fCleared = false;

        if (fFresh) { fClock = clkTgt; fFresh = false; }

        const float invSr   = 1.0f / sr;
        const float minClk  = 0.5f * 2048.0f / kMaxDelay;
        const float hiss    = 2.5e-4f;       // about -72 dBFS

        for (uint32_t i = 0; i < frames; ++i)
        {
            fInGain  += fFadeCoef * (inTarget  - fInGain);
            fWetGain += fFadeCoef * (wetTarget - fWetGain);
            fDryGain += fFadeCoef * (dryTarget - fDryGain);

            const float x = in[i];

            // --- noise chorus: 1.6 Hz low-pass, diode clamp, 0.5 Hz high-pass
            fNoiseZ += fNoiseLp * (rnd() * fNoiseNorm - fNoiseZ);
            const float nc = softClip(0.7f * fNoiseZ);
            fNoiseH += fNoiseHp * (nc - fNoiseH);
            const float drift = nc - fNoiseH;

            // --- clock: Speed with glide, plus the drift in Hz ----------------
            fClock += fGlideCoef * (clkTgt - fClock);
            float clk = fClock + chorusHz * drift;
            if (clk < minClk) clk = minClk;
            const float inc = clk * invSr;

            // --- input stage: sum, anti-alias filter, bucket clip, coupling ---
            float s = x * vol * fInGain + fDurBus;
            s = fIn2.process(fIn1.process(s));
            s = bucketClip(s);
            const float dc = s - fDcX + (1.0f - fDcCoef) * fDcY;   // 20 Hz high-pass
            fDcX = s; fDcY = dc;
            s = dc + kAntiDenormal;

            // --- clock ticks that fall inside this host sample ------------------
            fPhase += inc;
            while (fPhase >= 1.0f) {
                fPhase -= 1.0f;
                const float t = 1.0f - fPhase / inc;          // where in this sample
                const float v = fPrevIn + (s - fPrevIn) * t;
                fLine[fWrite & kLineMask] = v + hiss * rnd();
                for (int k = 0; k < 4; ++k) {
                    fTapPrev[k] = fTapCur[k];
                    fTapCur[k]  = fLine[(fWrite - tapSlots[k]) & kLineMask];
                }
                ++fWrite;
            }
            fPrevIn = s;

            // --- taps at host rate, then per-pair losses -------------------------
            float tap[4];
            for (int k = 0; k < 4; ++k) {
                float y = fTapPrev[k] + (fTapCur[k] - fTapPrev[k]) * fPhase;
                const uint32_t n = pairsPerTap * (uint32_t)(k + 1);
                for (uint32_t p = 0; p < n; ++p) {
                    fPairZ[k][p] += fPairCoef * (y - fPairZ[k][p]);
                    y = fPairZ[k][p];
                }
                tap[k] = y;
            }

            // --- matrix: Return (wet) bus and Duration (feedback) bus ----------
            float wet = 0.0f, fb = 0.0f;
            for (int k = 0; k < 4; ++k) { wet += wWet[k] * tap[k]; fb += wFb[k] * tap[k]; }
            fDurBus = fb;

            // output stage (T617-T619) runs out of headroom around 0 dBFS
            wet = softClip(fOut2.process(fOut1.process(wet)) * retGain) * fWetGain;

            outMix[i] = fDryGain * x + wet;
            outEch[i] = wet;
        }

        // one-pole smoothers stall a hair short of target in float: land them
        if (std::fabs(fInGain  - inTarget)  < 1e-4f) fInGain  = inTarget;
        if (std::fabs(fWetGain - wetTarget) < 1e-4f) fWetGain = wetTarget;
        if (std::fabs(fDryGain - dryTarget) < 1e-4f) fDryGain = dryTarget;
    }

private:
    float fParams[kParameterCount];

    std::vector<float> fLine;
    uint32_t fWrite = 0;
    float fPhase = 0.0f, fPrevIn = 0.0f, fClock = 10000.0f;
    float fTapPrev[4] = {}, fTapCur[4] = {};
    float fPairZ[4][8] = {};
    float fDurBus = 0.0f, fDcX = 0.0f, fDcY = 0.0f;

    Biquad fIn1, fIn2, fOut1, fOut2;

    float fSr = 48000.0f;
    float fPairCoef = 0.0f, fDcCoef = 0.0f, fGlideCoef = 0.0f, fFadeCoef = 0.0f;
    float fNoiseLp = 0.0f, fNoiseHp = 0.0f, fNoiseNorm = 1.0f, fNoiseZ = 0.0f, fNoiseH = 0.0f;
    uint32_t fSeed = 0x2801977u;

    float fInGain = 1.0f, fWetGain = 1.0f, fDryGain = 1.0f;
    bool  fCleared = true;
    bool  fFresh = true;

    DISTRHO_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(EC280Plugin)
};

Plugin* createPlugin() { return new EC280Plugin(); }

END_NAMESPACE_DISTRHO
