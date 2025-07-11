let participantData = {
    id: '',
    ageRange: '',
    gender: '',
    studyGroup: '',
    startTime: null,
    endTime: null,
    videoInteractions: [],
    questionResponses: [],
    segmentInteractions: [],
    totalInteractions: 0,
    // Video timing data
    videoWatchTime: 0, //video playing
    sessionDuration: 0, //page session
    videoSessionStartTime: null,
    videoSessionEndTime: null,  //SPECIFIC INTERACTIONS COUNTERS 
        playCount: 0,
        pauseCount: 0,
        seekCount: 0,
        rewindCount: 0,
        forwardCount: 0,
    // Playback speed tracking
    speedChanges: [], // Track when speed was changed
    speedUsage: {}, // Track duration spent at each speed (e.g., "1": 120000, "2": 30000)
    // Multi-video session data
    currentVideoIndex: 0, // 0 for first video, 1 for second video
    firstVideoData: null, // Store first video's data separately
    secondVideoData: null // Store second video's data separately
};

let currentQuestionIndex = 0;
let questionStartTime = null;
let studyStartTime = null;
let videoWatched = false;

//iming variables
let videoPlayStartTime = null;
let totalVideoPlayTime = 0;
let lastVideoTime = 0;
let sessionTimer = null;
let watchTimer = null;

// Playback speed tracking variables
let currentPlaybackSpeed = 1.0;
let speedStartTime = null;
let lastSpeedUsageUpdate = null;

// Study group configuration
let studyGroupConfig = null;
let currentVideoSegments = [];
let currentQuestions = [];

//INSERT VIDEO SEGMENTS here 
//Video segments are now loaded dynamically from JSON files based on study group config
const videoSegments = [
    // ERROR fallback segments - these should NOT be displayed if JSON loading works correctly
    { name: "ERROR: Segments failed to load", start: 0 },
    { name: "Check JSON file path", start: 30 },
    { name: "Verify config is correct", start: 60 }
]
//survey
//Questions are now loaded dynamically from JSON files based on study group config
const questions = [
    // ERROR fallback questions - these should NOT be displayed if JSON loading works correctly
    {
        id: 1,
        question: "ERROR: Questions failed to load from JSON file. If you see this, the questionnaire loading system is not working correctly.",
        type: "multiple-choice",
        options: [
            "JSON file not found",
            "Network error loading questions",
            "Invalid JSON format",
            "Configuration error"
        ],
        correctAnswer: 0
    }
];

//variables
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Set up event listeners
    document.getElementById('participant-form').addEventListener('submit', startStudy);
    document.getElementById('start-questions').addEventListener('click', startIntegratedQuestions);
    document.getElementById('toggle-questions').addEventListener('click', toggleQuestionsSection);
    document.getElementById('admin-toggle').addEventListener('click', toggleAdminPanel);
    document.getElementById('close-admin').addEventListener('click', closeAdminPanel);
    document.getElementById('download-data').addEventListener('click', downloadParticipantData);
    document.getElementById('export-all-data').addEventListener('click', exportAllData);
    document.getElementById('clear-data').addEventListener('click', clearAllData);
    document.getElementById('reset-study').addEventListener('click', resetStudy);
    document.getElementById('toggle-stats').addEventListener('click', toggleStatsPanel);
    
    // Add transition section event listeners
    document.getElementById('download-first-video-data').addEventListener('click', downloadFirstVideoData);
    document.getElementById('start-second-video').addEventListener('click', startSecondVideo);

    //load stats
    updateAdminStats();
    
    // Initialize participant ID
    initializeParticipantId();
}

async function startStudy(event) {
    event.preventDefault();
    
    // Collect participant information
    // participantData.id is already set from the generated ID
    participantData.ageRange = document.getElementById('participantAge').value;
    participantData.gender = document.getElementById('participantGender').value;
    participantData.studyGroup = document.getElementById('studyGroup').value;
    participantData.startTime = new Date();
    studyStartTime = Date.now();
    
    // Load study group configuration
    try {
        await loadStudyGroupConfig(participantData.studyGroup);
    } catch (error) {
        alert('Error loading study configuration. Please try again.');
        console.error('Error loading study config:', error);
        return;
    }
    
    // Start with the first video
    participantData.currentVideoIndex = 0;
    await loadCurrentVideo();
    
    // Hide participant setup and show video section
    document.getElementById('participant-setup').style.display = 'none';
    document.getElementById('video-section').style.display = 'block';
    document.getElementById('video-section').classList.add('fade-in');
    
    // Show questions section by default (no longer requires video completion)
    document.getElementById('integrated-questions-section').style.display = 'block';
    document.getElementById('integrated-questions-section').classList.add('fade-in');
    
    // Start video session timing
    participantData.videoSessionStartTime = Date.now();
    startSessionTimer();
    
    // Initialize video tracking
    initializeVideoTracking();
    // createVideoSegments() is now called in loadCurrentVideo() after segments are loaded
    
    // Initialize speed controls after a slight delay to ensure elements are rendered
    setTimeout(() => {
        initializeSpeedControls();
        console.log('Speed controls initialized from startStudy');
    }, 100);
}

function initializeVideoTracking() {
    const video = document.getElementById('main-video');
    
    // Track specific video events with detailed information
    const trackVideoEvent = (eventType, additionalData = {}) => {
        const currentTime = video.currentTime;
        const currentTimestamp = Date.now();
        const interaction = {
            type: eventType,
            timestamp: currentTimestamp,
            relativeTimestamp: formatRelativeTimestamp(currentTimestamp, participantData.videoSessionStartTime),
            videoTime: currentTime,
            relativeTime: currentTimestamp - studyStartTime,
            ...additionalData
        };
        
        participantData.videoInteractions.push(interaction);
        participantData.totalInteractions++;
        
        // Update specific interaction counters
        switch(eventType) {
            case 'play':
                participantData.playCount++;
                startVideoPlayTimer();
                break;
            case 'pause':
                participantData.pauseCount++;
                stopVideoPlayTimer();
                break;
            case 'seek':
                participantData.seekCount++;
                // Determine if it's rewind or forward
                const timeDiff = currentTime - lastVideoTime;
                if (timeDiff < -2) { // Rewound by more than 2 seconds
                    participantData.rewindCount++;
                    interaction.seekDirection = 'backward';
                    interaction.seekAmount = Math.abs(timeDiff);
                } else if (timeDiff > 2) { // Forwarded by more than 2 seconds
                    participantData.forwardCount++;
                    interaction.seekDirection = 'forward';
                    interaction.seekAmount = timeDiff;
                }
                break;
        }
        
        lastVideoTime = currentTime;
        updateInteractionCounter();
        updateVideoTimingDisplay();
    };

    // Video event listeners with specific tracking
    video.addEventListener('play', () => trackVideoEvent('play'));
    video.addEventListener('pause', () => trackVideoEvent('pause'));
    video.addEventListener('seeked', () => trackVideoEvent('seek'));
    
    // Track when video ends
    video.addEventListener('ended', () => {
        trackVideoEvent('ended');
        stopVideoPlayTimer();
    });
    
    // Track video progress
    video.addEventListener('timeupdate', function() {
        updateVideoProgress();
    });
    
    video.addEventListener('loadedmetadata', function() {
        // Video metadata loaded - duration now available if needed
    });
    
    video.addEventListener('durationchange', function() {
        // Duration changed - handle if needed
    });
    
    // Initialize playback speed controls
    initializeSpeedControls();
}

function createVideoSegments() {
    const segmentsContainer = document.getElementById('video-segments');
    segmentsContainer.innerHTML = '<h3>Video Segments</h3>';
    
    // Use currentVideoSegments loaded from JSON files
    const segments = currentVideoSegments.length > 0 ? currentVideoSegments : videoSegments;
    
    segments.forEach((segment, index) => {
        const button = document.createElement('button');
        button.className = 'segment-button';
        button.textContent = `${segment.name} (${formatTime(segment.start)})`;
        button.addEventListener('click', () => jumpToSegment(segment, index));
        segmentsContainer.appendChild(button);
    });
}

function jumpToSegment(segment, index) {
    const video = document.getElementById('main-video');
    video.currentTime = segment.start;
    
    // Track segment interaction
    const currentTimestamp = Date.now();
    const segmentInteraction = {
        segmentIndex: index,
        segmentName: segment.name,
        timestamp: currentTimestamp,
        relativeTimestamp: formatRelativeTimestamp(currentTimestamp, participantData.videoSessionStartTime),
        relativeTime: currentTimestamp - studyStartTime
    };
    
    participantData.segmentInteractions.push(segmentInteraction);
    participantData.totalInteractions++;
    updateInteractionCounter();
    
    // Update segment button states
    document.querySelectorAll('.segment-button').forEach((btn, i) => {
        btn.classList.toggle('active', i === index);
    });
}

function updateVideoProgress() {
    const video = document.getElementById('main-video');
    // Video progress tracking - duration display removed for cleaner UI
}

function checkVideoCompletion() {
    // No longer required - questions are available immediately
    // This function is kept for compatibility but does nothing
}

function toggleQuestionsSection() {
    const content = document.getElementById('questions-collapsible-content');
    const button = document.getElementById('toggle-questions');
    
    if (content.classList.contains('collapsed')) {
        // Expand
        content.classList.remove('collapsed');
        button.textContent = 'Hide Questions';
    } else {
        // Collapse
        content.classList.add('collapsed');
        button.textContent = 'Show Questions';
    }
}

function updateInteractionCounter() {
    updateVideoTimingDisplay();
}

function startIntegratedQuestions() {
    document.querySelector('.questions-prompt').style.display = 'none';
    document.getElementById('questions-content').style.display = 'block';
    renderCurrentQuestion();
}

function showQuestions() {
    //DO NOT REMOVE EVEN IF DEPRECATED
    //questions are now are shown directly below the video (not seperate webpage)
    startIntegratedQuestions();
}

function renderCurrentQuestion() {
    if (currentQuestionIndex >= currentQuestions.length) {
        completeStudy();
        return;
    }
    
    const question = currentQuestions[currentQuestionIndex];
    const container = document.getElementById('questions-container');
    
    questionStartTime = Date.now();
    
    container.innerHTML = `
        <div class="question">
            <h3>Question ${currentQuestionIndex + 1} of ${currentQuestions.length}</h3>
            <p>${question.question}</p>
            <div class="question-options" id="question-options">
                ${renderQuestionOptions(question)}
            </div>
            <div class="confidence-section" id="confidence-section">
                <div class="confidence-header">How confident are you in your answer?</div>
                <div class="confidence-row">
                    <span class="confidence-label-left">NOT CONFIDENT</span>
                    <div class="confidence-radio-group">
                        <div class="confidence-options">
                            ${[1,2,3,4,5].map(val => `
                                <label class="confidence-radio">
                                    <input type="radio" name="confidence" value="${val}">
                                    <span class="confidence-num">${val}</span>
                                </label>
                            `).join('')}
                        </div>
                    </div>
                    <span class="confidence-label-right">VERY CONFIDENT</span>
                </div>
            </div>
            <div class="question-timer">
                Time: <span id="question-timer">00:00</span>
            </div>
            <button id="next-question" class="btn btn-primary" style="margin-top: 20px; display: none;">
                ${currentQuestionIndex === currentQuestions.length - 1 ? 'Complete Study' : 'Next Question'}
            </button>
        </div>
    `;
    
    startQuestionTimer();
    setupQuestionInteraction(question);
}

function renderQuestionOptions(question) {
    if (question.type === 'multiple-choice') {
        return question.options.map((option, index) => `
            <div class="question-option" data-index="${index}">
                <input type="radio" name="q${question.id}" value="${index}" id="option${index}">
                <label for="option${index}">${option}</label>
            </div>
        `).join('');
    } else if (question.type === 'text') {
        return `
            <textarea id="text-answer" placeholder="Please provide your answer here..." rows="4"></textarea>
        `;
    }
}

function setupQuestionInteraction(question) {
    let answerSelected = false;
    let confidenceSelected = false;
    const nextBtn = document.getElementById('next-question');

    function updateNextButtonState() {
        if (answerSelected && confidenceSelected) {
            nextBtn.style.display = 'block';
        } else {
            nextBtn.style.display = 'none';
        }
    }

    if (question.type === 'multiple-choice') {
        document.querySelectorAll('.question-option').forEach(option => {
            option.addEventListener('click', function() {
                const radio = this.querySelector('input[type="radio"]');
                radio.checked = true;
                document.querySelectorAll('.question-option').forEach(opt => {
                    opt.classList.remove('selected');
                });
                this.classList.add('selected');
                answerSelected = true;
                updateNextButtonState();
            });
        });
    } else if (question.type === 'text') {
        const textarea = document.getElementById('text-answer');
        textarea.addEventListener('input', function() {
            answerSelected = this.value.trim().length > 0;
            updateNextButtonState();
        });
    }

    document.querySelectorAll('input[name="confidence"]').forEach(radio => {
        radio.addEventListener('change', function() {
            confidenceSelected = true;
            updateNextButtonState();
        });
    });

    nextBtn.addEventListener('click', submitAnswer);
}

function startQuestionTimer() {
    const timerElement = document.getElementById('question-timer');
    const startTime = Date.now();
    
    const timer = setInterval(() => {
        const elapsed = Date.now() - startTime;
        timerElement.textContent = formatTime(elapsed / 1000);
    }, 1000);
    
    // Store timer to clear it later
    timerElement.timerId = timer;
}

function submitAnswer() {
    const question = currentQuestions[currentQuestionIndex];
    const completionTime = Date.now() - questionStartTime;
    
    let answer = null;
    let isCorrect = null;
    
    if (question.type === 'multiple-choice') {
        const selectedOption = document.querySelector('input[name="q' + question.id + '"]:checked');
        if (selectedOption) {
            answer = parseInt(selectedOption.value);
            isCorrect = question.correctAnswer !== null ? answer === question.correctAnswer : null;
        }
    } else if (question.type === 'text') {
        answer = document.getElementById('text-answer').value.trim();
        isCorrect = null; // Text answers require manual evaluation
    }
    
    // Get confidence value
    const confidenceRadio = document.querySelector('input[name="confidence"]:checked');
    const confidence = confidenceRadio ? parseInt(confidenceRadio.value) : null;

    // Store question response
    const currentTimestamp = Date.now();
    const response = {
        questionId: question.id,
        questionType: question.type,
        answer: answer,
        isCorrect: isCorrect,
        confidence: confidence,
        completionTime: completionTime,
        completionTimeFormatted: formatTimeWithMilliseconds(completionTime),
        timestamp: currentTimestamp,
        relativeTimestamp: formatRelativeTimestamp(currentTimestamp, participantData.videoSessionStartTime)
    };
    
    participantData.questionResponses.push(response);
    
    // Clear timer
    const timerElement = document.getElementById('question-timer');
    if (timerElement.timerId) {
        clearInterval(timerElement.timerId);
    }
    
    // Move to next question
    currentQuestionIndex++;
    renderCurrentQuestion();
}

function completeStudy() {
    participantData.endTime = new Date();
    stopVideoPlayTimer();
    stopSessionTimer();
    participantData.videoSessionEndTime = Date.now();
    participantData.sessionDuration = participantData.videoSessionEndTime - participantData.videoSessionStartTime;
    
    //RECORD FINAL TIME
    participantData.videoWatchTime = totalVideoPlayTime;
    
    // Check if this is the first video or second video
    if (participantData.currentVideoIndex === 0) {
        // First video completed - show transition section
        document.getElementById('video-section').style.display = 'none';
        document.getElementById('transition-section').style.display = 'block';
        document.getElementById('transition-section').classList.add('fade-in');
        
        // Set participant ID in transition section
        document.getElementById('transition-participant-id').textContent = participantData.id;
        
        console.log('First video completed, showing transition section');
    } else {
        // Second video completed - show final completion section
        document.getElementById('video-section').style.display = 'none';
        document.getElementById('completion-section').style.display = 'block';
        document.getElementById('completion-section').classList.add('fade-in');
        
        // Display completion statistics
        updateCompletionStats();
        
        // Set participant ID in completion section
        document.getElementById('completion-participant-id').value = participantData.id;
        
        // Add copy functionality for completion section ID
        setupCompletionIdCopy();
        
        console.log('Second video completed, showing final completion section');
    }
    
    // Save data to localStorage
    saveParticipantData();
}

function updateCompletionStats() {
    const totalTime = participantData.endTime - participantData.startTime;
    
    // Calculate combined statistics if this is the second video
    let combinedStats = {
        totalInteractions: participantData.totalInteractions,
        questionsAnswered: participantData.questionResponses.length,
        playCount: participantData.playCount,
        pauseCount: participantData.pauseCount,
        seekCount: participantData.seekCount,
        rewindCount: participantData.rewindCount,
        forwardCount: participantData.forwardCount,
        speedChanges: participantData.speedChanges ? participantData.speedChanges.length : 0,
        speedUsage: participantData.speedUsage || {},
        videoWatchTime: participantData.videoWatchTime,
        sessionDuration: participantData.sessionDuration
    };
    
    if (participantData.currentVideoIndex === 1 && participantData.firstVideoData) {
        // Combine data from both videos
        combinedStats = {
            totalInteractions: participantData.totalInteractions + participantData.firstVideoData.totalInteractions,
            questionsAnswered: participantData.questionResponses.length + participantData.firstVideoData.questionResponses.length,
            playCount: participantData.playCount + participantData.firstVideoData.playCount,
            pauseCount: participantData.pauseCount + participantData.firstVideoData.pauseCount,
            seekCount: participantData.seekCount + participantData.firstVideoData.seekCount,
            rewindCount: participantData.rewindCount + participantData.firstVideoData.rewindCount,
            forwardCount: participantData.forwardCount + participantData.firstVideoData.forwardCount,
            speedChanges: (participantData.speedChanges ? participantData.speedChanges.length : 0) + 
                         (participantData.firstVideoData.speedChanges ? participantData.firstVideoData.speedChanges.length : 0),
            videoWatchTime: participantData.videoWatchTime + participantData.firstVideoData.videoWatchTime,
            sessionDuration: participantData.sessionDuration + participantData.firstVideoData.sessionDuration,
            speedUsage: {...participantData.speedUsage}
        };
        
        // Combine speed usage
        if (participantData.firstVideoData.speedUsage) {
            Object.keys(participantData.firstVideoData.speedUsage).forEach(speed => {
                if (combinedStats.speedUsage[speed]) {
                    combinedStats.speedUsage[speed] += participantData.firstVideoData.speedUsage[speed];
                } else {
                    combinedStats.speedUsage[speed] = participantData.firstVideoData.speedUsage[speed];
                }
            });
        }
    }
    
    document.getElementById('total-time').textContent = formatTimeForDisplay(totalTime);
    document.getElementById('final-interactions').textContent = combinedStats.totalInteractions;
    document.getElementById('questions-answered').textContent = combinedStats.questionsAnswered;
    
    //speed usage tracking
    const statsContainer = document.getElementById('completion-section');
    const existingDetails = statsContainer.querySelector('.interaction-details');
    if (!existingDetails) {
        let speedUsageHtml = '';
        const usedSpeeds = Object.keys(combinedStats.speedUsage || {}).filter(speed => combinedStats.speedUsage[speed] > 0);
        if (usedSpeeds.length > 0) {
            speedUsageHtml = '<h4>Speed Usage Breakdown</h4>';
            usedSpeeds.forEach(speed => {
                const duration = combinedStats.speedUsage[speed];
                const formattedTime = formatTimeForDisplay(duration);
                speedUsageHtml += `
                    <div class="stat-item">
                        <strong>${speed}x Speed:</strong> ${formattedTime}
                    </div>
                `;
            });
        }
        
        const detailsDiv = document.createElement('div');
        detailsDiv.className = 'interaction-details';
        detailsDiv.innerHTML = `
            <h3>Detailed Interaction Summary ${participantData.currentVideoIndex === 1 ? '(Combined from Both Videos)' : ''}</h3>
            <div class="stats-grid">
                <div class="stat-item">
                    <strong>Video Watch Time:</strong> ${formatTimeForDisplay(combinedStats.videoWatchTime)}
                </div>
                <div class="stat-item">
                    <strong>Session Duration:</strong> ${formatTimeForDisplay(combinedStats.sessionDuration)}
                </div>
                <div class="stat-item">
                    <strong>Play Actions:</strong> ${combinedStats.playCount}
                </div>
                <div class="stat-item">
                    <strong>Pause Actions:</strong> ${combinedStats.pauseCount}
                </div>
                <div class="stat-item">
                    <strong>Scrubbing:</strong> ${combinedStats.seekCount}
                </div>
                <div class="stat-item">
                    <strong>Rewind Actions:</strong> ${combinedStats.rewindCount}
                </div>
                <div class="stat-item">
                    <strong>Forward Actions:</strong> ${combinedStats.forwardCount}
                </div>
                <div class="stat-item">
                    <strong>Speed Changes:</strong> ${combinedStats.speedChanges}
                </div>
            </div>
            ${speedUsageHtml}
        `;
        statsContainer.appendChild(detailsDiv);
    }
}

function saveParticipantData() {
    const speedUsageFormatted = {};
    const speedUsageIndividual = {};
    
    Object.keys(participantData.speedUsage || {}).forEach(speed => {
        if (participantData.speedUsage[speed] > 0) {
            speedUsageFormatted[`${speed}x`] = formatTimeWithMilliseconds(participantData.speedUsage[speed]);
            speedUsageIndividual[`${speed}xFormatted`] = formatTimeWithMilliseconds(participantData.speedUsage[speed]);
        }
    });
    
    const formattedData = {
        ...participantData,
        videoWatchTimeFormatted: formatTimeWithMilliseconds(participantData.videoWatchTime),
        sessionDurationFormatted: formatTimeWithMilliseconds(participantData.sessionDuration),
        speedUsageFormatted: speedUsageFormatted,
        ...speedUsageIndividual, // Add individual formatted speed times to main object
        videoWatchTime: participantData.videoWatchTime,
        sessionDuration: participantData.sessionDuration
    };
    
    const allData = JSON.parse(localStorage.getItem('researchData') || '[]');
    allData.push(formattedData);
    localStorage.setItem('researchData', JSON.stringify(allData));
    updateAdminStats();
}

function downloadParticipantData() {
    let dataToDownload = participantData;
    let filename = `participant_${participantData.id}_data.json`;
    
    // If this is the final download (after second video), include combined data
    if (participantData.currentVideoIndex === 1 && participantData.firstVideoData) {
        dataToDownload = {
            ...participantData,
            // Mark this as the complete dataset
            completeDataset: true,
            firstVideoData: participantData.firstVideoData,
            secondVideoData: {
                videoInteractions: [...participantData.videoInteractions],
                questionResponses: [...participantData.questionResponses],
                segmentInteractions: [...participantData.segmentInteractions],
                totalInteractions: participantData.totalInteractions,
                videoWatchTime: participantData.videoWatchTime,
                playCount: participantData.playCount,
                pauseCount: participantData.pauseCount,
                seekCount: participantData.seekCount,
                rewindCount: participantData.rewindCount,
                forwardCount: participantData.forwardCount,
                speedChanges: [...participantData.speedChanges],
                speedUsage: {...participantData.speedUsage}
            }
        };
        filename = `participant_${participantData.id}_complete_data.json`;
    }
    
    const speedUsageFormatted = {};
    const speedUsageIndividual = {};
    
    Object.keys(dataToDownload.speedUsage || {}).forEach(speed => {
        if (dataToDownload.speedUsage[speed] > 0) {
            speedUsageFormatted[`${speed}x`] = formatTimeWithMilliseconds(dataToDownload.speedUsage[speed]);
            speedUsageIndividual[`${speed}xFormatted`] = formatTimeWithMilliseconds(dataToDownload.speedUsage[speed]);
        }
    });
    
    //participant data formatted times
    const formattedData = {
        ...dataToDownload,
        videoWatchTimeFormatted: formatTimeWithMilliseconds(dataToDownload.videoWatchTime),
        sessionDurationFormatted: formatTimeWithMilliseconds(dataToDownload.sessionDuration),
        speedUsageFormatted: speedUsageFormatted,
        ...speedUsageIndividual, 
        //original data
        videoWatchTime: dataToDownload.videoWatchTime,
        sessionDuration: dataToDownload.sessionDuration
    };
    
    const dataStr = JSON.stringify(formattedData, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = filename.replace('.json', `_${new Date().toISOString().split('T')[0]}.json`);
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
}

function resetStudy() {
    // Clear any running timers
    stopVideoPlayTimer();
    stopSessionTimer();
    
    // Reset all variables
    participantData = {
        id: '',
        ageRange: '',
        gender: '',
        startTime: null,
        endTime: null,
        videoInteractions: [],
        questionResponses: [],
        segmentInteractions: [],
        totalInteractions: 0,
        // Video timing data
        videoWatchTime: 0,
        sessionDuration: 0,
        videoSessionStartTime: null,
        videoSessionEndTime: null,
        // Specific interaction counters
        playCount: 0,
        pauseCount: 0,
        seekCount: 0,
        rewindCount: 0,
        forwardCount: 0,
        // Playback speed tracking
        speedChanges: [],
        speedUsage: {}
    };
    
    currentQuestionIndex = 0;
    questionStartTime = null;
    studyStartTime = null;
    videoWatched = false;
    
    // Reset video timing variables
    videoPlayStartTime = null;
    totalVideoPlayTime = 0;
    lastVideoTime = 0;
    sessionTimer = null;
    watchTimer = null;
    
    // Reset speed tracking variables
    currentPlaybackSpeed = 1.0;
    speedStartTime = null;
    lastSpeedUsageUpdate = null;
    
    // Reset form
    document.getElementById('participant-form').reset();
    
    // Regenerate participant ID
    initializeParticipantId();
    
    // Show participant setup
    document.getElementById('completion-section').style.display = 'none';
    document.getElementById('video-section').style.display = 'none';
    document.getElementById('integrated-questions-section').style.display = 'none';
    document.getElementById('participant-setup').style.display = 'block';
    
    // Reset integrated questions section
    document.querySelector('.questions-prompt').style.display = 'block';
    document.getElementById('questions-content').style.display = 'none';
    
    // Reset questions section toggle state
    const questionsContent = document.getElementById('questions-collapsible-content');
    const questionsToggle = document.getElementById('toggle-questions');
    if (questionsContent && questionsToggle) {
        questionsContent.classList.remove('collapsed');
        questionsToggle.textContent = 'Hide Questions';
    }
    
    // Reset video
    const video = document.getElementById('main-video');
    video.currentTime = 0;
    video.playbackRate = 1.0; // Reset speed to normal
    
    document.getElementById('speed-selector').value = '1';
    document.getElementById('current-speed-display').textContent = 'Current: 1x';
    
    // Hide stats panel and reset button text
    document.getElementById('stats-panel').style.display = 'none';
    document.getElementById('toggle-stats').textContent = 'Show Stats';
    
    // Remove interaction details if they exist
    const existingDetails = document.querySelector('.interaction-details');
    if (existingDetails) {
        existingDetails.remove();
    }
}

// Admin functions
function toggleAdminPanel() {
    document.getElementById('admin-panel').style.display = 'flex';
}

function closeAdminPanel() {
    document.getElementById('admin-panel').style.display = 'none';
}

function updateAdminStats() {
    const allData = JSON.parse(localStorage.getItem('researchData') || '[]');
    
    document.getElementById('admin-total-participants').textContent = allData.length;
    
    if (allData.length > 0) {
        const avgTime = allData.reduce((sum, participant) => {
            return sum + (new Date(participant.endTime) - new Date(participant.startTime));
        }, 0) / allData.length;
        
        const avgInteractions = allData.reduce((sum, participant) => {
            return sum + participant.totalInteractions;
        }, 0) / allData.length;
        
        document.getElementById('admin-avg-time').textContent = formatTimeForDisplay(avgTime);
        document.getElementById('admin-avg-interactions').textContent = Math.round(avgInteractions);
    }
}

function exportAllData() {
    const allData = JSON.parse(localStorage.getItem('researchData') || '[]');
    
    //find all speeds used by partcipant (eg. 1x , 1.5x, 2x etc)
    const allSpeedsUsed = new Set();
    allData.forEach(participant => {
        if (participant.speedUsage) {
            Object.keys(participant.speedUsage).forEach(speed => {
                if (participant.speedUsage[speed] > 0) {
                    allSpeedsUsed.add(speed);
                }
            });
        }
    });
    const speedColumns = Array.from(allSpeedsUsed).sort((a, b) => parseFloat(a) - parseFloat(b));
    
    // Create enhanced CSV format for analysis
    let csvHeader = "Participant ID,Age Range,Gender,Total Time (ms),Total Time (formatted),Video Watch Time (ms),Video Watch Time (formatted),Session Duration (ms),Session Duration (formatted),Video Interactions,Segment Interactions,Questions Answered,Accuracy Rate,Play Count,Pause Count,Scrubbing Count,Rewind Count,Forward Count";
    
    //speed usage
    speedColumns.forEach(speed => {
        csvHeader += `,${speed}x Speed (ms),${speed}x Speed (formatted)`;
    });
    csvHeader += "\n";
    
    let csvContent = csvHeader;
    
    allData.forEach(participant => {
        const totalTime = (new Date(participant.endTime) - new Date(participant.startTime));
        const totalTimeFormatted = formatTimeWithMilliseconds(totalTime);
        const videoWatchTime = participant.videoWatchTime || 0;
        const videoWatchTimeFormatted = participant.videoWatchTimeFormatted || formatTimeWithMilliseconds(videoWatchTime);
        const sessionDuration = participant.sessionDuration || 0;
        const sessionDurationFormatted = participant.sessionDurationFormatted || formatTimeWithMilliseconds(sessionDuration);
        const correctAnswers = participant.questionResponses.filter(q => q.isCorrect === true).length;
        const totalAnswered = participant.questionResponses.filter(q => q.isCorrect !== null).length;
        const accuracyRate = totalAnswered > 0 ? (correctAnswers / totalAnswered * 100).toFixed(1) : 'N/A';
        
        let row = `${participant.id},${participant.ageRange || participant.age},${participant.gender},${totalTime},${totalTimeFormatted},${videoWatchTime},${videoWatchTimeFormatted},${sessionDuration},${sessionDurationFormatted},${participant.videoInteractions.length},${participant.segmentInteractions.length},${participant.questionResponses.length},${accuracyRate}%,${participant.playCount || 0},${participant.pauseCount || 0},${participant.seekCount || 0},${participant.rewindCount || 0},${participant.forwardCount || 0}`;
        
        // Add speed usage data
        speedColumns.forEach(speed => {
            const speedUsage = (participant.speedUsage && participant.speedUsage[speed]) || 0;
            const speedUsageFormatted = formatTimeWithMilliseconds(speedUsage);
            row += `,${speedUsage},${speedUsageFormatted}`;
        });
        
        csvContent += row + "\n";
    });
    
    // Also export detailed JSON data
    const jsonDataStr = JSON.stringify(allData, null, 2);
    
    // Download CSV
    const csvUri = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csvContent);
    const csvLink = document.createElement('a');
    csvLink.setAttribute('href', csvUri);
    csvLink.setAttribute('download', `research_data_summary_${new Date().toISOString().split('T')[0]}.csv`);
    csvLink.click();
    
    // Download JSON
    setTimeout(() => {
        const jsonUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(jsonDataStr);
        const jsonLink = document.createElement('a');
        jsonLink.setAttribute('href', jsonUri);
        jsonLink.setAttribute('download', `research_data_detailed_${new Date().toISOString().split('T')[0]}.json`);
        jsonLink.click();
    }, 1000);
}

function clearAllData() {
    if (confirm('Are you sure you want to clear all participant data? This action cannot be undone.')) {
        localStorage.removeItem('researchData');
        updateAdminStats();
        alert('All data has been cleared.');
    }
}

// Video timing functions
function startSessionTimer() {
    if (sessionTimer) clearInterval(sessionTimer);
    
    sessionTimer = setInterval(() => {
        updateVideoTimingDisplay();
    }, 1000); // Update every second
}

function stopSessionTimer() {
    if (sessionTimer) {
        clearInterval(sessionTimer);
        sessionTimer = null;
    }
}

function startVideoPlayTimer() {
    if (!videoPlayStartTime) {
        videoPlayStartTime = Date.now();
        speedStartTime = Date.now(); // Reset speed tracking when play starts
        if (!participantData.speedUsage) {
            participantData.speedUsage = {};
        }
        if (!participantData.speedUsage[currentPlaybackSpeed.toString()]) {
            participantData.speedUsage[currentPlaybackSpeed.toString()] = 0;
        }
        
        // Start watch timer that updates every second
        if (watchTimer) clearInterval(watchTimer);
        watchTimer = setInterval(() => {
            if (videoPlayStartTime) {
                const currentPlayTime = Date.now() - videoPlayStartTime;
                participantData.videoWatchTime = totalVideoPlayTime + currentPlayTime;
                
                // Update speed usage for current session
                updateSpeedUsageForCurrentSession();
                
                updateVideoTimingDisplay();
            }
        }, 1000);
    }
}

function stopVideoPlayTimer() {
    if (videoPlayStartTime) {
        const playDuration = Date.now() - videoPlayStartTime;
        totalVideoPlayTime += playDuration;
        participantData.videoWatchTime = totalVideoPlayTime;
        
        // Update final speed usage for this play session
        updateSpeedUsage();
        
        videoPlayStartTime = null;
        speedStartTime = null; // Reset speed timing when video is paused
        
        // Stop watch timer
        if (watchTimer) {
            clearInterval(watchTimer);
            watchTimer = null;
        }
    }
}

function updateVideoTimingDisplay() {
    // Calculate current session duration
    const sessionDuration = participantData.videoSessionStartTime ? 
        Date.now() - participantData.videoSessionStartTime : 0;
    
    // Calculate current watch time (including any active play session)
    let currentWatchTime = totalVideoPlayTime;
    if (videoPlayStartTime) {
        currentWatchTime += (Date.now() - videoPlayStartTime);
    }

    const timingInfo = ` | Session: ${formatTimeForDisplay(sessionDuration)} | Watch: ${formatTimeForDisplay(currentWatchTime)}`;
    document.getElementById('interaction-count').textContent = 
        `Interactions: ${participantData.totalInteractions}${timingInfo}`;
    
    // Update live stats panel if visible
    updateLiveStatsPanel(sessionDuration, currentWatchTime);
}

// Stats panel functions
function toggleStatsPanel() {
    const statsPanel = document.getElementById('stats-panel');
    const toggleButton = document.getElementById('toggle-stats');
    
    if (statsPanel.style.display === 'none' || statsPanel.style.display === '') {
        statsPanel.style.display = 'block';
        statsPanel.classList.add('slide-down');
        toggleButton.textContent = 'Hide Stats';
        updateLiveStatsPanel();
    } else {
        statsPanel.style.display = 'none';
        statsPanel.classList.remove('slide-down');
        toggleButton.textContent = 'Show Stats';
    }
}

function updateLiveStatsPanel(sessionDuration = null, currentWatchTime = null) {
    const statsPanel = document.getElementById('stats-panel');
    if (statsPanel.style.display === 'none') return;
    
    // Calculate session duration if not provided
    if (sessionDuration === null) {
        sessionDuration = participantData.videoSessionStartTime ? 
            Date.now() - participantData.videoSessionStartTime : 0;
    }
    
    // Calculate current watch time if not provided
    if (currentWatchTime === null) {
        currentWatchTime = totalVideoPlayTime;
        if (videoPlayStartTime) {
            currentWatchTime += (Date.now() - videoPlayStartTime);
        }
    }
    
    // Update all live stats
    document.getElementById('live-session-time').textContent = formatTimeForDisplay(sessionDuration);
    document.getElementById('live-watch-time').textContent = formatTimeForDisplay(currentWatchTime);
    document.getElementById('live-total-interactions').textContent = participantData.totalInteractions;
    document.getElementById('live-play-count').textContent = participantData.playCount;
    document.getElementById('live-pause-count').textContent = participantData.pauseCount;
    document.getElementById('live-seek-count').textContent = participantData.seekCount;
    document.getElementById('live-rewind-count').textContent = participantData.rewindCount;
    document.getElementById('live-forward-count').textContent = participantData.forwardCount;
    document.getElementById('live-segment-count').textContent = participantData.segmentInteractions.length;
    
    // Update speed-related stats
    if (document.getElementById('live-current-speed')) {
        document.getElementById('live-current-speed').textContent = currentPlaybackSpeed + 'x';
    }
    if (document.getElementById('live-speed-changes')) {
        document.getElementById('live-speed-changes').textContent = participantData.speedChanges ? participantData.speedChanges.length : 0;
    }
    updateSpeedUsageDisplay();
}

//playback speed controls
function initializeSpeedControls() {
    const video = document.getElementById('main-video');
    const speedSelector = document.getElementById('speed-selector');
    const customSpeedInput = document.getElementById('custom-speed');
    const currentSpeedDisplay = document.getElementById('current-speed-display');
    
    // Check if elements exist
    if (!speedSelector || !customSpeedInput || !currentSpeedDisplay) {
        console.error('Speed control elements not found');
        return;
    }
    
    console.log('Initializing speed controls');
    
    // Initialize speed tracking - don't set speedStartTime until video starts playing
    if (!participantData.speedUsage) {
        participantData.speedUsage = {};
    }
    participantData.speedUsage['1'] = 0; // Start with normal speed
    
    speedSelector.addEventListener('change', function() {
        console.log('Speed selector changed to:', this.value);
        if (this.value === 'custom') {
            customSpeedInput.style.display = 'inline-block';
            customSpeedInput.focus();
        } else {
            customSpeedInput.style.display = 'none';
            const newSpeed = parseFloat(this.value);
            setVideoPlaybackSpeed(newSpeed);
        }
    });
    
    customSpeedInput.addEventListener('change', function() {
        const customSpeed = parseFloat(this.value);
        console.log('Custom speed input:', customSpeed);
        if (customSpeed >= 0.1 && customSpeed <= 5) {
            setVideoPlaybackSpeed(customSpeed);
        } else {
            alert('Please enter a speed between 0.1 and 5.0');
            this.value = '';
        }
    });
    
    customSpeedInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            this.blur(); // Trigger change event
        }
    });
}

function setVideoPlaybackSpeed(newSpeed) {
    const video = document.getElementById('main-video');
    const currentSpeedDisplay = document.getElementById('current-speed-display');
    
    console.log('setVideoPlaybackSpeed called with:', newSpeed);
    console.log('Video element:', video);
    console.log('Current speed display element:', currentSpeedDisplay);
    
    if (!video) {
        console.error('Video element not found');
        return;
    }
    
    if (!currentSpeedDisplay) {
        console.error('Current speed display element not found');
        return;
    }
    updateSpeedUsage();
    
    //track speed change
    const currentTimestamp = Date.now();
    const speedChange = {
        type: 'speed_change',
        timestamp: currentTimestamp,
        relativeTimestamp: formatRelativeTimestamp(currentTimestamp, participantData.videoSessionStartTime),
        videoTime: video.currentTime,
        previousSpeed: currentPlaybackSpeed,
        newSpeed: newSpeed,
        relativeTime: currentTimestamp - studyStartTime
    };
    
    participantData.videoInteractions.push(speedChange);
    
    // Initialize speedChanges array if it doesn't exist
    if (!participantData.speedChanges) {
        participantData.speedChanges = [];
    }
    participantData.speedChanges.push(speedChange);
    participantData.totalInteractions++;
    
    // Set the actual video playback rate
    video.playbackRate = newSpeed;
    currentPlaybackSpeed = newSpeed;
    
    console.log('Video playback rate set to:', video.playbackRate);
    console.log('currentPlaybackSpeed variable set to:', currentPlaybackSpeed);
    
    // Reset speed timing for new speed
    speedStartTime = Date.now();
    if (!participantData.speedUsage) {
        participantData.speedUsage = {};
    }
    if (!participantData.speedUsage[newSpeed.toString()]) {
        participantData.speedUsage[newSpeed.toString()] = 0;
    }
    
    // Update display
    currentSpeedDisplay.textContent = `Current: ${newSpeed}x`;
    console.log('Display updated to:', currentSpeedDisplay.textContent);
    
    // Update interaction counter and stats
    updateInteractionCounter();
    updateLiveStatsPanel();
    
    console.log(`Speed changed to ${newSpeed}x, video.playbackRate = ${video.playbackRate}`);
}

// Test function for debugging
function testSpeedChange() {
    console.log('Test button clicked');
    const video = document.getElementById('main-video');
    const display = document.getElementById('current-speed-display');
    
    console.log('Video element:', video);
    console.log('Display element:', display);
    
    if (video) {
        video.playbackRate = 2.0;
        console.log('Video playback rate set to:', video.playbackRate);
    }
    
    if (display) {
        display.textContent = 'Current: 2x';
        console.log('Display text updated');
    }
    
    currentPlaybackSpeed = 2.0;
    console.log('currentPlaybackSpeed variable set to:', currentPlaybackSpeed);
}

// Study Group Configuration Functions
async function loadStudyGroupConfig(groupId) {
    try {
        const response = await fetch(`config/group${groupId}/group${groupId}_config.json`);
        if (!response.ok) {
            throw new Error(`Failed to load group ${groupId} configuration`);
        }
        studyGroupConfig = await response.json();
        console.log('Loaded study group config:', studyGroupConfig);
    } catch (error) {
        console.error('Error loading study group config:', error);
        throw error;
    }
}

async function loadCurrentVideo() {
    if (!studyGroupConfig) {
        throw new Error('Study group configuration not loaded');
    }
    
    const videoInfo = participantData.currentVideoIndex === 0 
        ? studyGroupConfig.firstVideo 
        : studyGroupConfig.secondVideo;
    
    // Update video title
    const videoHeader = document.querySelector('.video-header h2');
    videoHeader.textContent = `Video: ${videoInfo.title}`;
    
    // Update video source
    const video = document.getElementById('main-video');
    const source = video.querySelector('source');
    source.src = `video/${videoInfo.filename}`;
    video.load(); // Reload the video with new source
    
    // Load segments for current video
    await loadVideoSegments(videoInfo);
    
    // Create video segments UI after segments are loaded
    createVideoSegments();
    
    // Load questions for current video (if exists)
    await loadVideoQuestions(videoInfo);
}

async function loadVideoSegments(videoInfo) {
    try {
        // Construct path based on segmentType from individual video config
        let segmentPath;
        if (videoInfo.segmentType === "root") {
            segmentPath = `config/group${participantData.studyGroup}/${videoInfo.segmentsFile}`;
        } else {
            segmentPath = `config/group${participantData.studyGroup}/${videoInfo.segmentType}/${videoInfo.segmentsFile}`;
        }
        
        const response = await fetch(segmentPath);
        if (!response.ok) {
            throw new Error(`Failed to load segments file: ${segmentPath}`);
        }
        currentVideoSegments = await response.json();
        console.log('Loaded video segments:', currentVideoSegments);
    } catch (error) {
        console.error('Error loading video segments:', error);
        // Fallback to default segments if file doesn't exist
        currentVideoSegments = videoSegments;
    }
}

async function loadVideoQuestions(videoInfo) {
    try {
        // Try to load questionnaire file for this video
        const questionnaireFile = videoInfo.segmentsFile.replace('_segments.json', '_questionnaire.json');
        
        // Construct path based on segmentType from individual video config
        let questionnairePath;
        if (videoInfo.segmentType === "root") {
            questionnairePath = `config/group${participantData.studyGroup}/${questionnaireFile}`;
        } else {
            // For files in subdirectories like 'creator', questionnaire files are in root
            questionnairePath = `config/group${participantData.studyGroup}/${questionnaireFile}`;
        }
        
        const response = await fetch(questionnairePath);
        if (!response.ok) {
            throw new Error(`Failed to load questionnaire file: ${questionnairePath}`);
        }
        currentQuestions = await response.json();
        console.log('Loaded video questions:', currentQuestions);
    } catch (error) {
        console.error('Error loading video questions:', error);
        // Fallback to default questions if file doesn't exist
        currentQuestions = questions;
    }
}

function downloadFirstVideoData() {
    // Save current video data before transitioning
    participantData.firstVideoData = {
        videoInteractions: [...participantData.videoInteractions],
        questionResponses: [...participantData.questionResponses],
        segmentInteractions: [...participantData.segmentInteractions],
        totalInteractions: participantData.totalInteractions,
        videoWatchTime: participantData.videoWatchTime,
        playCount: participantData.playCount,
        pauseCount: participantData.pauseCount,
        seekCount: participantData.seekCount,
        rewindCount: participantData.rewindCount,
        forwardCount: participantData.forwardCount,
        speedChanges: [...participantData.speedChanges],
        speedUsage: {...participantData.speedUsage}
    };
    
    // Download the first video data
    const firstVideoData = {
        ...participantData,
        videoNumber: 1,
        downloadTime: new Date().toISOString()
    };
    
    const dataStr = JSON.stringify(firstVideoData, null, 2);
    const dataBlob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `participant_${participantData.id}_video1_data.json`;
    link.click();
    URL.revokeObjectURL(url);
    
    console.log('First video data downloaded');
}

async function startSecondVideo() {
    // Reset video-specific data for second video
    participantData.currentVideoIndex = 1;
    participantData.videoInteractions = [];
    participantData.questionResponses = [];
    participantData.segmentInteractions = [];
    participantData.totalInteractions = 0;
    participantData.videoWatchTime = 0;
    participantData.playCount = 0;
    participantData.pauseCount = 0;
    participantData.seekCount = 0;
    participantData.rewindCount = 0;
    participantData.forwardCount = 0;
    participantData.speedChanges = [];
    participantData.speedUsage = {};
    
    // Reset question state
    currentQuestionIndex = 0;
    videoWatched = false;
    
    // Load second video configuration
    await loadCurrentVideo();
    
    // Hide transition section and show video section
    document.getElementById('transition-section').style.display = 'none';
    document.getElementById('video-section').style.display = 'block';
    
    // createVideoSegments() is now called in loadCurrentVideo() after segments are loaded
    
    // Reset questions section
    resetQuestionsSection();
    
    // Restart video session timing
    participantData.videoSessionStartTime = Date.now();
    startSessionTimer();
    
    // Re-initialize video tracking
    initializeVideoTracking();
    
    console.log('Started second video');
}

function resetQuestionsSection() {
    // Reset questions display
    const questionsContent = document.getElementById('questions-content');
    const questionsPrompt = document.querySelector('.questions-prompt');
    
    questionsContent.style.display = 'none';
    questionsPrompt.style.display = 'block';
    
    // Clear questions container
    const questionsContainer = document.getElementById('questions-container');
    questionsContainer.innerHTML = '';
    
    // Reset toggle button
    const toggleButton = document.getElementById('toggle-questions');
    toggleButton.textContent = 'Hide Questions';
}

// Utility Functions
function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function formatTimeForDisplay(milliseconds) {
    const totalSeconds = Math.floor(milliseconds / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

function formatTimeWithMilliseconds(milliseconds) {
    const totalSeconds = Math.floor(milliseconds / 1000);
    const ms = milliseconds % 1000;
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}:${ms.toString().padStart(3, '0')}`;
}

function formatRelativeTimestamp(timestamp, sessionStartTime) {
    const relativeTime = timestamp - sessionStartTime;
    return formatTime(relativeTime / 1000);
}

function updateSpeedUsageForCurrentSession() {
    if (!speedStartTime || !videoPlayStartTime) return; // Only track when video is actually playing
    
    const currentTime = Date.now();
    const elapsedTime = currentTime - speedStartTime;
    
    // Initialize speed usage object if needed
    if (!participantData.speedUsage) {
        participantData.speedUsage = {};
    }
    
    // Update speed usage for the current speed
    const speedKey = currentPlaybackSpeed.toString();
    if (participantData.speedUsage[speedKey]) {
        participantData.speedUsage[speedKey] += elapsedTime;
    } else {
        participantData.speedUsage[speedKey] = elapsedTime;
    }
    
    // Reset timing for the next interval
    speedStartTime = currentTime;
}

function updateSpeedUsage() {
    if (!speedStartTime || !videoPlayStartTime) return; // Only track when video is actually playing
    
    const currentTime = Date.now();
    const elapsedTime = currentTime - speedStartTime;
    
    // Initialize speed usage object if needed
    if (!participantData.speedUsage) {
        participantData.speedUsage = {};
    }
    
    // Update speed usage for the current speed
    const speedKey = currentPlaybackSpeed.toString();
    if (participantData.speedUsage[speedKey]) {
        participantData.speedUsage[speedKey] += elapsedTime;
    } else {
        participantData.speedUsage[speedKey] = elapsedTime;
    }
    
    // Reset timing for the next interval
    speedStartTime = currentTime;
}

function updateSpeedUsageDisplay() {
    const speedUsageList = document.getElementById('speed-usage-list');
    if (!speedUsageList) return;
    
    let html = '';
    const usedSpeeds = Object.keys(participantData.speedUsage || {}).filter(speed => participantData.speedUsage[speed] > 0);
    
    if (usedSpeeds.length === 0) {
        html = '<div class="speed-usage-item">No speed data yet</div>';
    } else {
        usedSpeeds.forEach(speed => {
            const duration = participantData.speedUsage[speed];
            const formattedTime = formatTimeForDisplay(duration);
            html += `<div class="speed-usage-item">
                <span class="speed-label">${speed}x Speed:</span>
                <span class="speed-duration">${formattedTime}</span>
            </div>`;
        });
    }
    
    speedUsageList.innerHTML = html;
}

// Generate a random participant ID
function generateParticipantId() {
    const timestamp = Date.now().toString(36); // Base36 timestamp for uniqueness
    const randomChars = Math.random().toString(36).substring(2, 8); // 6 random characters
    return `P${timestamp}${randomChars}`.toUpperCase();
}

// Initialize participant ID on page load
function initializeParticipantId() {
    const participantId = generateParticipantId();
    document.getElementById('participantId').value = participantId;
    participantData.id = participantId;
    
    // Add copy functionality
    document.getElementById('copy-id-btn').addEventListener('click', function() {
        const idInput = document.getElementById('participantId');
        idInput.select();
        idInput.setSelectionRange(0, 99999); // For mobile devices
        
        try {
            document.execCommand('copy');
            
            // Visual feedback
            const copyBtn = this;
            const originalText = copyBtn.textContent;
            copyBtn.textContent = 'Copied!';
            copyBtn.classList.add('copied');
            
            setTimeout(() => {
                copyBtn.textContent = originalText;
                copyBtn.classList.remove('copied');
            }, 2000);
        } catch (err) {
            console.error('Failed to copy text: ', err);
        }
    });
}

function setupCompletionIdCopy() {
    const copyBtn = document.getElementById('copy-completion-id-btn');
    if (copyBtn) {
        // Remove any existing event listeners to avoid duplicates
        copyBtn.replaceWith(copyBtn.cloneNode(true));
        const newCopyBtn = document.getElementById('copy-completion-id-btn');
        
        newCopyBtn.addEventListener('click', function() {
            const idInput = document.getElementById('completion-participant-id');
            idInput.select();
            idInput.setSelectionRange(0, 99999); // For mobile devices
            
            try {
                document.execCommand('copy');
                
                // Visual feedback
                const originalText = this.textContent;
                this.textContent = 'Copied!';
                this.classList.add('copied');
                
                setTimeout(() => {
                    this.textContent = originalText;
                    this.classList.remove('copied');
                }, 2000);
            } catch (err) {
                console.error('Failed to copy text: ', err);
            }
        });
    }
}