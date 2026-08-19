
export const state = {
    // Documents
    currentDoc: null,
    currentPages: [],
    
    // Decoupled Pointers
    readingPageIndex: 0,    // Where the voice is
    readingSentences: [],   // The sentences being spoken
    currentSentenceIndex: 0, // Current line index
    viewPageIndex: 0,       // What the user is seeing
    viewSentences: [],      // The sentences currently rendered on screen
    
    sentenceElements: [],   // Cache for current view
    smartStartPage: 0,
    autoScrollEnabled: true,

    // Playback
    isPlaying: false,
    audioContext: null,
    currentAudioSource: null,
    audioBufferCache: new Map(),
    MAX_AUDIO_CACHE: 10,

    // Settings
    rules: [],
    ignoreList: [],
    headerFooterMode: 'off',
    engineMode: 'gpu',
    currentSearchQuery: '',
    searchDebounceTimer: null,
    jumpTimer: null,
    // Intra-sentence marks default to 0 so the model renders the sentence in one
    // piece and produces its own comma and colon prosody. A non-zero value here
    // forces a hard split at that mark and inserts literal silence, which is
    // occasionally wanted but costs the natural intonation across the sentence.
    pauseSettings: { comma: 0, period: 600, question: 600, exclamation: 600, colon: 0, semicolon: 0, newline: 0 },

    // Voices & Language
    currentLangIndex: 0,
    currentTranslations: {},
    languages: ['en', 'fr', 'es', 'zh'],
    defaultVoices: {
        'en': 'af_bella',
        'fr': 'ff_siwis',
        'es': 'ef_dora',
        'zh': 'zf_xiaobei'
    }
};
