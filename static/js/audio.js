/**
 * Deepbuster Audio Synthesizer Engine
 * Synthesizes system feedback sounds using the Web Audio API without media dependencies.
 */

class AudioSynth {
    constructor() {
        this.ctx = null;
        this.enabled = true;
    }

    init() {
        if (this.ctx) return;
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.ctx = new AudioContext();
        } catch (e) {
            console.error("Web Audio API not supported:", e);
        }
    }

    playOscillator(freq, duration, type = 'sine', sweepTo = null, vol = 0.1) {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;
        
        // Resume context if suspended
        if (this.ctx.state === 'suspended') {
            this.ctx.resume();
        }

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        
        osc.type = type;
        osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
        
        if (sweepTo) {
            osc.frequency.exponentialRampToValueAtTime(sweepTo, this.ctx.currentTime + duration);
        }

        gain.gain.setValueAtTime(vol, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, this.ctx.currentTime + duration);

        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.start();
        osc.stop(this.ctx.currentTime + duration);
    }

    playStart() {
        // Futuristic swept up note
        this.playOscillator(150, 0.4, 'triangle', 600, 0.15);
    }

    playFinding() {
        // High pitch diagnostic double-beep
        this.playOscillator(880, 0.08, 'sine', null, 0.08);
        setTimeout(() => {
            this.playOscillator(1200, 0.12, 'sine', null, 0.08);
        }, 100);
    }

    playError() {
        // Low feedback alert sweep
        this.playOscillator(280, 0.25, 'sawtooth', 120, 0.12);
    }

    playComplete() {
        // Melodic success chime
        const notes = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6
        notes.forEach((freq, idx) => {
            setTimeout(() => {
                this.playOscillator(freq, 0.5, 'sine', null, 0.1);
            }, idx * 120);
        });
    }
}

// Global instance
window.synth = new AudioSynth();
