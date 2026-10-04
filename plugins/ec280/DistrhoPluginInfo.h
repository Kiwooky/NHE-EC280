#ifndef DISTRHO_PLUGIN_INFO_H_INCLUDED
#define DISTRHO_PLUGIN_INFO_H_INCLUDED

#define DISTRHO_PLUGIN_BRAND       "New Horizon Electronics"
#define DISTRHO_PLUGIN_NAME        "Electronic Echo 280"
#define DISTRHO_PLUGIN_URI         "https://github.com/Kiwooky/NHE-EC280"

#define DISTRHO_PLUGIN_HAS_UI       0
#define DISTRHO_PLUGIN_IS_RT_SAFE   1
#define DISTRHO_PLUGIN_NUM_INPUTS   1
#define DISTRHO_PLUGIN_NUM_OUTPUTS  2

enum Parameters {
    kVolume = 0,
    kSpeed,
    kDuration,
    kReturn,
    kChorus,
    kMode,
    kEchoTaps,
    kHallTaps,
    kRange,
    kTails,
    kBypass,
    kParameterCount
};

#endif
