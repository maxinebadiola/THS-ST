let participantData = {
    name: '',
    age: 0,
    gender: '',
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
        forwardCount: 0
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

//INSERT VIDEO SEGMENTS here 
//TODO: get segments via .csv or .json
const videoSegments = [
    { name: "Introduction", start: 0, end: 30 },
    { name: "Weather Conditions", start: 30, end: 120 },
    { name: "Fire Behavior", start: 120, end: 240 },
    { name: "Emergency Response", start: 240, end: 360 },
    { name: "Community Impact", start: 360, end: 480 },
    { name: "Lessons Learned", start: 480, end: 600 },
    { name: "Lessons Learned", start: 480, end: 600 },
    { name: "Lessons Learned", start: 480, end: 600 },
    { name: "Lessons Learned", start: 480, end: 600 },
    { name: "Lessons Learned", start: 480, end: 600 }
]
//survey
//TODO: get segments via .json
const questions = [
    {
        id: 1,
        question: "What were the primary weather conditions that contributed to the severity of Black Saturday?",
        type: "multiple-choice",
        options: [
            "High temperatures and strong winds",
            "Heavy rainfall and flooding",
            "Snow and freezing temperatures",
            "Mild conditions with light breeze"
        ],
        correctAnswer: 0
    },
    {
        id: 2,
        question: "How did the fire behavior differ from typical bushfires?",
        type: "multiple-choice",
        options: [
            "It moved slower than usual",
            "It created its own weather system",
            "It only burned at night",
            "It was easily contained"
        ],
        correctAnswer: 1
    }
];

//variables
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Set up event listeners
    document.getElementById('participant-form').addEventListener('submit', startStudy);
    document.getElementById('proceed-to-questions').addEventListener('click', showQuestions);
    document.getElementById('admin-toggle').addEventListener('click', toggleAdminPanel);
    document.getElementById('close-admin').addEventListener('click', closeAdminPanel);
    document.getElementById('download-data').addEventListener('click', downloadParticipantData);
    document.getElementById('export-all-data').addEventListener('click', exportAllData);
    document.getElementById('clear-data').addEventListener('click', clearAllData);
    document.getElementById('reset-study').addEventListener('click', resetStudy);
    document.getElementById('toggle-stats').addEventListener('click', toggleStatsPanel);

    //load stats
    updateAdminStats();
}

function startStudy(event) {
    event.preventDefault();
    
    // Collect participant information
    participantData.name = document.getElementById('participantName').value;
    participantData.age = parseInt(document.getElementById('participantAge').value);
    participantData.gender = document.getElementById('participantGender').value;
    participantData.startTime = new Date();
    studyStartTime = Date.now();
    
    // Hide participant setup and show video section
    document.getElementById('participant-setup').style.display = 'none';
    document.getElementById('video-section').style.display = 'block';
    document.getElementById('video-section').classList.add('fade-in');
    
    // Start video session timing
    participantData.videoSessionStartTime = Date.now();
    startSessionTimer();
    
    // Initialize video tracking
    initializeVideoTracking();
    createVideoSegments();
}

function initializeVideoTracking() {
    const video = document.getElementById('main-video');
    
    // Track specific video events with detailed information
    const trackVideoEvent = (eventType, additionalData = {}) => {
        const currentTime = video.currentTime;
        const interaction = {
            type: eventType,
            timestamp: Date.now(),
            videoTime: currentTime,
            relativeTime: Date.now() - studyStartTime,
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
        checkVideoCompletion();
    });
    
    video.addEventListener('loadedmetadata', function() {
        // Video metadata loaded - duration now available if needed
    });
    
    video.addEventListener('durationchange', function() {
        // Duration changed - handle if needed
    });
}

function createVideoSegments() {
    const segmentsContainer = document.getElementById('video-segments');
    segmentsContainer.innerHTML = '<h3>Video Segments</h3>';
    
    videoSegments.forEach((segment, index) => {
        const button = document.createElement('button');
        button.className = 'segment-button';
        button.textContent = `${segment.name} (${formatTime(segment.start)} - ${formatTime(segment.end)})`;
        button.addEventListener('click', () => jumpToSegment(segment, index));
        segmentsContainer.appendChild(button);
    });
}

function jumpToSegment(segment, index) {
    const video = document.getElementById('main-video');
    video.currentTime = segment.start;
    
    // Track segment interaction
    const segmentInteraction = {
        segmentIndex: index,
        segmentName: segment.name,
        timestamp: Date.now(),
        relativeTime: Date.now() - studyStartTime
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
    const video = document.getElementById('main-video');
    const watchThreshold = 0.8; // 80% of video watched
    
    if (video.currentTime / video.duration >= watchThreshold && !videoWatched) {
        videoWatched = true;
        document.getElementById('proceed-to-questions').style.display = 'block';
        document.getElementById('proceed-to-questions').classList.add('pulse');
    }
}

function updateInteractionCounter() {
    updateVideoTimingDisplay();
}

function showQuestions() {
    // Stop video timing when moving to questions
    stopVideoPlayTimer();
    stopSessionTimer();
    participantData.videoSessionEndTime = Date.now();
    participantData.sessionDuration = participantData.videoSessionEndTime - participantData.videoSessionStartTime;
    
    // Ensure final watch time is recorded
    participantData.videoWatchTime = totalVideoPlayTime;
    
    document.getElementById('video-section').style.display = 'none';
    document.getElementById('questions-section').style.display = 'block';
    document.getElementById('questions-section').classList.add('fade-in');
    
    renderCurrentQuestion();
}

function renderCurrentQuestion() {
    if (currentQuestionIndex >= questions.length) {
        completeStudy();
        return;
    }
    
    const question = questions[currentQuestionIndex];
    const container = document.getElementById('questions-container');
    
    questionStartTime = Date.now();
    
    container.innerHTML = `
        <div class="question">
            <h3>Question ${currentQuestionIndex + 1} of ${questions.length}</h3>
            <p>${question.question}</p>
            <div class="question-options" id="question-options">
                ${renderQuestionOptions(question)}
            </div>
            <div class="question-timer">
                Time: <span id="question-timer">00:00</span>
            </div>
            <button id="next-question" class="btn btn-primary" style="margin-top: 20px; display: none;">
                ${currentQuestionIndex === questions.length - 1 ? 'Complete Study' : 'Next Question'}
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
    if (question.type === 'multiple-choice') {
        document.querySelectorAll('.question-option').forEach(option => {
            option.addEventListener('click', function() {
                const radio = this.querySelector('input[type="radio"]');
                radio.checked = true;
                
                document.querySelectorAll('.question-option').forEach(opt => {
                    opt.classList.remove('selected');
                });
                this.classList.add('selected');
                
                document.getElementById('next-question').style.display = 'block';
            });
        });
    } else if (question.type === 'text') {
        const textarea = document.getElementById('text-answer');
        textarea.addEventListener('input', function() {
            if (this.value.trim().length > 10) {
                document.getElementById('next-question').style.display = 'block';
            }
        });
    }
    
    document.getElementById('next-question').addEventListener('click', submitAnswer);
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
    const question = questions[currentQuestionIndex];
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
    
    // Store question response
    const response = {
        questionId: question.id,
        questionType: question.type,
        answer: answer,
        isCorrect: isCorrect,
        completionTime: completionTime,
        timestamp: Date.now()
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
    
    document.getElementById('questions-section').style.display = 'none';
    document.getElementById('completion-section').style.display = 'block';
    document.getElementById('completion-section').classList.add('fade-in');
    
    // Display completion statistics
    updateCompletionStats();
    
    // Save data to localStorage
    saveParticipantData();
}

function updateCompletionStats() {
    const totalTime = participantData.endTime - participantData.startTime;
    
    document.getElementById('total-time').textContent = formatTime(totalTime / 1000);
    document.getElementById('final-interactions').textContent = participantData.totalInteractions;
    document.getElementById('questions-answered').textContent = participantData.questionResponses.length;
    
    // Add detailed interaction breakdown
    const statsContainer = document.getElementById('completion-section');
    const existingDetails = statsContainer.querySelector('.interaction-details');
    if (!existingDetails) {
        const detailsDiv = document.createElement('div');
        detailsDiv.className = 'interaction-details';
        detailsDiv.innerHTML = `
            <h3>Detailed Interaction Summary</h3>
            <div class="stats-grid">
                <div class="stat-item">
                    <strong>Video Watch Time:</strong> ${formatTime(participantData.videoWatchTime / 1000)}
                </div>
                <div class="stat-item">
                    <strong>Session Duration:</strong> ${formatTime(participantData.sessionDuration / 1000)}
                </div>
                <div class="stat-item">
                    <strong>Play Actions:</strong> ${participantData.playCount}
                </div>
                <div class="stat-item">
                    <strong>Pause Actions:</strong> ${participantData.pauseCount}
                </div>
                <div class="stat-item">
                    <strong>Scrubbing:</strong> ${participantData.seekCount}
                </div>
                <div class="stat-item">
                    <strong>Rewind Actions:</strong> ${participantData.rewindCount}
                </div>
                <div class="stat-item">
                    <strong>Forward Actions:</strong> ${participantData.forwardCount}
                </div>
            </div>
        `;
        statsContainer.appendChild(detailsDiv);
    }
}

function saveParticipantData() {
    const allData = JSON.parse(localStorage.getItem('researchData') || '[]');
    allData.push(participantData);
    localStorage.setItem('researchData', JSON.stringify(allData));
    updateAdminStats();
}

function downloadParticipantData() {
    const dataStr = JSON.stringify(participantData, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `participant_${participantData.name}_${new Date().toISOString().split('T')[0]}.json`;
    
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
        name: '',
        age: 0,
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
        forwardCount: 0
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
    
    // Reset form
    document.getElementById('participant-form').reset();
    
    // Show participant setup
    document.getElementById('completion-section').style.display = 'none';
    document.getElementById('participant-setup').style.display = 'block';
    
    // Reset video
    const video = document.getElementById('main-video');
    video.currentTime = 0;
    document.getElementById('proceed-to-questions').style.display = 'none';
    
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
        
        document.getElementById('admin-avg-time').textContent = formatTime(avgTime / 1000);
        document.getElementById('admin-avg-interactions').textContent = Math.round(avgInteractions);
    }
}

function exportAllData() {
    const allData = JSON.parse(localStorage.getItem('researchData') || '[]');
    
    // Create enhanced CSV format for analysis
    let csvContent = "Participant Name,Age,Gender,Total Time (seconds),Video Watch Time (seconds),Session Duration (seconds),Video Interactions,Segment Interactions,Questions Answered,Accuracy Rate,Play Count,Pause Count,Scrubbing Count,Rewind Count,Forward Count\n";
    
    allData.forEach(participant => {
        const totalTime = (new Date(participant.endTime) - new Date(participant.startTime)) / 1000;
        const videoWatchTime = (participant.videoWatchTime || 0) / 1000;
        const sessionDuration = (participant.sessionDuration || 0) / 1000;
        const correctAnswers = participant.questionResponses.filter(q => q.isCorrect === true).length;
        const totalAnswered = participant.questionResponses.filter(q => q.isCorrect !== null).length;
        const accuracyRate = totalAnswered > 0 ? (correctAnswers / totalAnswered * 100).toFixed(1) : 'N/A';
        
        csvContent += `${participant.name},${participant.age},${participant.gender},${totalTime},${videoWatchTime},${sessionDuration},${participant.videoInteractions.length},${participant.segmentInteractions.length},${participant.questionResponses.length},${accuracyRate}%,${participant.playCount || 0},${participant.pauseCount || 0},${participant.seekCount || 0},${participant.rewindCount || 0},${participant.forwardCount || 0}\n`;
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
        
        // Start watch timer that updates every second
        if (watchTimer) clearInterval(watchTimer);
        watchTimer = setInterval(() => {
            if (videoPlayStartTime) {
                const currentPlayTime = Date.now() - videoPlayStartTime;
                participantData.videoWatchTime = totalVideoPlayTime + currentPlayTime;
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
        videoPlayStartTime = null;
        
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
    
    const timingInfo = ` | Session: ${formatTime(sessionDuration / 1000)} | Watch: ${formatTime(currentWatchTime / 1000)}`;
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
    document.getElementById('live-session-time').textContent = formatTime(sessionDuration / 1000);
    document.getElementById('live-watch-time').textContent = formatTime(currentWatchTime / 1000);
    document.getElementById('live-total-interactions').textContent = participantData.totalInteractions;
    document.getElementById('live-play-count').textContent = participantData.playCount;
    document.getElementById('live-pause-count').textContent = participantData.pauseCount;
    document.getElementById('live-seek-count').textContent = participantData.seekCount;
    document.getElementById('live-rewind-count').textContent = participantData.rewindCount;
    document.getElementById('live-forward-count').textContent = participantData.forwardCount;
    document.getElementById('live-segment-count').textContent = participantData.segmentInteractions.length;
}

// Utility functions
function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
}

// Prevent accidental page refresh during study
window.addEventListener('beforeunload', function (e) {
    if (studyStartTime && !participantData.endTime) {
        e.preventDefault();
        e.returnValue = '';
        return 'Are you sure you want to leave? Your progress will be lost.';
    }
});

// Auto-save functionality for data integrity
setInterval(() => {
    if (studyStartTime && participantData.name) {
        const tempData = {...participantData, tempSave: true, lastSaved: new Date()};
        localStorage.setItem('tempParticipantData', JSON.stringify(tempData));
    }
}, 30000); // Auto-save every 30 seconds
