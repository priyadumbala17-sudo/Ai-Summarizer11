import React, { useState } from 'react';
import { Video, Layout, Brain, Book, Cloud, Download, FileJson, Loader2, AlertCircle, CheckCircle, XCircle } from 'lucide-react';
import jsPDF from 'jspdf';

function App() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [results, setResults] = useState(null);
  const [quizAnswers, setQuizAnswers] = useState({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [quizResults, setQuizResults] = useState({});

  const handleAnalyze = async () => {
    if (!url.trim()) {
      setError('Please enter a YouTube URL');
      return;
    }

    setLoading(true);
    setError('');
    setResults(null);
    setQuizAnswers({});
    setQuizSubmitted(false);
    setQuizResults({});

    try {
      const response = await fetch('https://ai-summarizer-backend-io1r.onrender.com/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: url.trim() }),
      });

      const data = await response.json();
      console.log('Response received:', data);

      if (!response.ok) {
        throw new Error(data.error || 'Failed to analyze video');
      }

      console.log('Setting results:', data.sections);
      setResults(data);
    } catch (err) {
      console.error('Error:', err);
      setError(err.message || 'An error occurred while analyzing the video');
    } finally {
      setLoading(false);
    }
  };

  // PDF Export Function
  const handleExportPDF = () => {
    if (!results || !results.sections) {
      alert('No results to export. Please analyze a video first.');
      return;
    }

    try {
      const pdf = new jsPDF();
      const pageWidth = pdf.internal.pageSize.getWidth();
      let yPosition = 20;

      // Title
      pdf.setFontSize(20);
      pdf.setFont('helvetica', 'bold');
      pdf.text('AI Lecture Summary', pageWidth / 2, yPosition, { align: 'center' });
      yPosition += 15;

      // Model Info
      pdf.setFontSize(10);
      pdf.setFont('helvetica', 'normal');
      pdf.text(`Generated using: ${results.model_used || 'AI'}`, pageWidth / 2, yPosition, { align: 'center' });
      yPosition += 10;

      // Summary Section
      if (results.sections.summary) {
        if (yPosition > 250) {
          pdf.addPage();
          yPosition = 20;
        }
        
        pdf.setFontSize(16);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Summary', 10, yPosition);
        yPosition += 10;

        pdf.setFontSize(11);
        pdf.setFont('helvetica', 'normal');
        const summaryLines = results.sections.summary.split('\n').filter(line => line.trim());
        summaryLines.forEach((line) => {
          if (yPosition > 270) {
            pdf.addPage();
            yPosition = 20;
          }
          const cleanedLine = line.replace(/^•\s*/, '').replace(/^[-*]\s*/, '');
          const splitText = pdf.splitTextToSize(`• ${cleanedLine}`, pageWidth - 20);
          pdf.text(splitText, 10, yPosition);
          yPosition += splitText.length * 6 + 3;
        });
      }

      // Topics Section
      if (results.sections.timestamps) {
        if (yPosition > 250) {
          pdf.addPage();
          yPosition = 20;
        }

        pdf.setFontSize(16);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Topics Discussed', 10, yPosition);
        yPosition += 10;

        pdf.setFontSize(11);
        pdf.setFont('helvetica', 'normal');
        const topicLines = results.sections.timestamps.split('\n').filter(line => line.trim());
        topicLines.forEach((line) => {
          if (yPosition > 270) {
            pdf.addPage();
            yPosition = 20;
          }
          const cleanedLine = line.replace(/^\d{2}:\d{2}\s*-\s*/, '').replace(/^[-*]\s*/, '');
          pdf.text(`• ${cleanedLine}`, 10, yPosition);
          yPosition += 8;
        });
      }

      // Quiz Section
      if (results.sections.quiz) {
        if (yPosition > 250) {
          pdf.addPage();
          yPosition = 20;
        }

        pdf.setFontSize(16);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Self-Assessment Quiz', 10, yPosition);
        yPosition += 10;

        pdf.setFontSize(11);
        pdf.setFont('helvetica', 'normal');
        const quizLines = results.sections.quiz.split('\n\n').filter(q => q.trim());
        quizLines.forEach((question) => {
          if (yPosition > 260) {
            pdf.addPage();
            yPosition = 20;
          }
          const lines = question.split('\n').filter(line => line.trim());
          lines.forEach((line) => {
            if (yPosition > 270) {
              pdf.addPage();
              yPosition = 20;
            }
            const cleanedLine = line.replace(/\*\*/g, '');
            const splitText = pdf.splitTextToSize(cleanedLine, pageWidth - 20);
            pdf.text(splitText, 10, yPosition);
            yPosition += splitText.length * 6 + 2;
          });
          yPosition += 3;
        });
      }

      // Key Terms Section
      if (results.sections.key_terms) {
        if (yPosition > 250) {
          pdf.addPage();
          yPosition = 20;
        }

        pdf.setFontSize(16);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Key Terms', 10, yPosition);
        yPosition += 10;

        pdf.setFontSize(11);
        pdf.setFont('helvetica', 'normal');
        const termLines = results.sections.key_terms.split('\n').filter(line => line.trim());
        termLines.forEach((line) => {
          if (yPosition > 270) {
            pdf.addPage();
            yPosition = 20;
          }
          const cleanedLine = line.replace(/^-\s*\*\*/, '').replace(/\*\*:/, ':');
          const splitText = pdf.splitTextToSize(`• ${cleanedLine}`, pageWidth - 20);
          pdf.text(splitText, 10, yPosition);
          yPosition += splitText.length * 6 + 3;
        });
      }

      // Keywords Section
      if (results.sections.keywords) {
        if (yPosition > 250) {
          pdf.addPage();
          yPosition = 20;
        }

        pdf.setFontSize(16);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Keywords', 10, yPosition);
        yPosition += 10;

        pdf.setFontSize(11);
        pdf.setFont('helvetica', 'normal');
        const keywords = results.sections.keywords.split(',').map(k => k.trim());
        const keywordsText = keywords.join(', ');
        const splitKeywords = pdf.splitTextToSize(keywordsText, pageWidth - 20);
        splitKeywords.forEach((line) => {
          if (yPosition > 270) {
            pdf.addPage();
            yPosition = 20;
          }
          pdf.text(line, 10, yPosition);
          yPosition += 6;
        });
      }

      // Save PDF
      const fileName = `lecture-summary-${new Date().toISOString().slice(0, 10)}.pdf`;
      pdf.save(fileName);
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('Failed to generate PDF. Please try again.');
    }
  };

  // Quiz Handling Functions
  const handleOptionSelect = (questionIndex, optionIndex) => {
    if (quizSubmitted) return;
    setQuizAnswers(prev => ({
      ...prev,
      [questionIndex]: optionIndex
    }));
  };

  const handleSubmitQuiz = () => {
    if (Object.keys(quizAnswers).length === 0) {
      alert('Please select at least one answer before submitting.');
      return;
    }

    // Parse quiz data to get correct answers
    const quizText = results?.sections?.quiz || '';
    const questionBlocks = quizText.split('\n\n').filter(q => q.trim());
    const questions = [];
    
    questionBlocks.forEach((block, blockIndex) => {
      const lines = block.split('\n').filter(line => line.trim());
      const questionText = lines.find(line => line.match(/^Q\d+\./));
      const answerLine = lines.find(line => line.toLowerCase().includes('**answer:**'));
      const options = lines.filter(line => line.match(/^[A-D]\)/));
      
      if (questionText && options.length > 0) {
        let correctIndex = -1;
        if (answerLine) {
          const answerMatch = answerLine.match(/\*\*Answer:\*\*\s*([A-D])\)/i);
          if (answerMatch) {
            const correctLetter = answerMatch[1].toUpperCase();
            correctIndex = correctLetter.charCodeAt(0) - 65;
          }
        }
        
        questions.push({
          index: blockIndex,
          correctAnswer: correctIndex
        });
      }
    });

    // Evaluate answers
    const results_data = {};
    questions.forEach((q) => {
      const selectedOption = quizAnswers[q.index];
      const correctOption = q.correctAnswer;
      results_data[q.index] = {
        selected: selectedOption,
        correct: correctOption,
        isCorrect: selectedOption === correctOption
      };
    });

    setQuizResults(results_data);
    setQuizSubmitted(true);
  };

  const handleResetQuiz = () => {
    setQuizAnswers({});
    setQuizSubmitted(false);
    setQuizResults({});
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
      {/* Header Section [cite: 1, 2] */}
      <nav className="bg-white border-b border-slate-200 px-6 py-4 flex justify-between items-center sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <div className="bg-blue-600 p-2 rounded-lg text-white">
            <Brain size={24} />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-blue-900">AI-Powered Lecture Summarizer</h1>
        </div>
        <div className="flex gap-3">
          {results && results.model_used && (
            <div className={`px-3 py-1.5 border rounded-lg ${
              results.model_used.includes('demo') 
                ? 'bg-amber-100 border-amber-200' 
                : results.model_used.includes('Groq') || results.model_used.includes('groq')
                ? 'bg-green-100 border-green-200'
                : 'bg-blue-100 border-blue-200'
            }`}>
              <span className={`text-xs font-medium ${
                results.model_used.includes('demo') 
                ? 'text-amber-800' 
                : results.model_used.includes('Groq') || results.model_used.includes('groq')
                ? 'text-green-800'
                : 'text-blue-800'
              }`}>
                {results.model_used.includes('demo') ? '⚠ Demo Mode' : `✅ AI Analysis`}
              </span>
            </div>
          )}
          <button 
            onClick={() => {
              const json_data = JSON.stringify(results, null, 2);
              const blob = new Blob([json_data], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `lecture-summary-${new Date().toISOString().slice(0, 10)}.json`;
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-md transition"
          >
            <FileJson size={18} /> JSON
          </button>
          <button 
            onClick={handleExportPDF}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 rounded-md shadow-sm transition"
          >
            <Download size={18} /> Export PDF
          </button>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto p-6 lg:p-8">
        {/* Input Area [cite: 15] */}
        <section className="mb-12 text-center">
          <h2 className="text-3xl font-extrabold text-slate-800 mb-4">Transform Lectures into Study Material</h2>
          <div className="max-w-2xl mx-auto flex gap-3 shadow-xl p-2 bg-white rounded-2xl border border-slate-100">
            <div className="relative flex-1">
              <Video className="absolute left-4 top-3.5 text-red-500" size={20} />
              <input 
                type="text" 
                placeholder="Paste YouTube URL (e.g., https://youtube.com/watch?v=...)" 
                className="w-full pl-12 pr-4 py-3 bg-transparent outline-none text-slate-700"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </div>
            
            <button 
              onClick={handleAnalyze}
              disabled={loading}
              className="bg-slate-900 text-white px-8 py-3 rounded-xl font-semibold hover:bg-blue-600 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Analyzing...
                </>
              ) : (
                'Analyze'
              )}
            </button>
          </div>
          <p className="text-slate-500 mt-4 text-sm italic">Powered by AI with intelligent fallback</p>
          
          {/* Error Message */}
          {error && (
            <div className="max-w-2xl mx-auto mt-4 p-5 bg-amber-50 border border-amber-200 rounded-xl">
              <div className="flex items-start gap-3">
                <AlertCircle className="text-amber-600 flex-shrink-0 mt-0.5" size={20} />
                <div className="flex-1">
                  <p className="text-amber-800 font-semibold mb-2">Analysis Temporarily Unavailable</p>
                  <p className="text-amber-700 text-sm mb-3">{error}</p>
                  <div className="bg-white p-3 rounded-lg border border-amber-100">
                    <p className="text-xs text-amber-800 font-medium mb-2">What you can do:</p>
                    <ul className="text-xs text-amber-700 space-y-1">
                      <li>• Wait 1-2 minutes and try again</li>
                      <li>• The system automatically tries 3 different AI models</li>
                      <li>• This is a temporary issue with the AI service</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Feature Grid [cite: 24] */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content Column */}
          <div className="lg:col-span-2 space-y-8">
            <ContentCard title="Bullet-Point Summary" icon={<Layout className="text-green-600" />} badge="The 'What'">
              {results && results.sections && results.sections.summary ? (
                <ul className="space-y-3 text-slate-600">
                  {results.sections.summary.split('\n').filter(line => line.trim()).map((point, index) => (
                    <li key={index} className="flex gap-3">
                      <span className="text-green-600 font-bold">•</span>
                      <span className="text-slate-700">{point.replace(/^•\s*/, '')}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <ul className="space-y-3 text-slate-600">
                  <li className="flex gap-3"><span>•</span> 60-minute lectures condensed into 5-minute reads[cite: 11].</li>
                  <li className="flex gap-3"><span>•</span> 90% information retention for exam preparation[cite: 11].</li>
                </ul>
              )}
            </ContentCard>

            <ContentCard title="Self-Assessment Quiz" icon={<Brain className="text-purple-600" />} badge="The 'Recall'">
              {results && results.sections && results.sections.quiz ? (
                <QuizSection 
                  quizData={results.sections.quiz}
                  quizAnswers={quizAnswers}
                  quizSubmitted={quizSubmitted}
                  quizResults={quizResults}
                  onOptionSelect={handleOptionSelect}
                  onSubmitQuiz={handleSubmitQuiz}
                  onResetQuiz={handleResetQuiz}
                />
              ) : (
                <>
                  <p className="text-slate-500 italic text-sm mb-4">Auto-generated MCQs to promote active recall.</p>
                  <div className="p-4 border border-dashed border-slate-200 rounded-lg text-center text-slate-400">
                    Quiz questions will appear here after analysis.
                  </div>
                </>
              )}
            </ContentCard>
          </div>

          {/* Sidebar Column */}
          <div className="space-y-8">
            <ContentCard title="Topics Discussed" icon={<Book className="text-orange-500" />} badge="The 'What'">
              {results && results.sections && results.sections.timestamps ? (
                <div className="space-y-3">
                  {results.sections.timestamps.split('\n').filter(line => line.trim()).map((topic, index) => {
                    // Remove timestamp if present, show only topic name
                    const match = topic.match(/\d{2}:\d{2}\s*-\s*(.+)/);
                    const topicName = match ? match[1] : topic.replace(/^[-*]\s*/, '');
                    return (
                      <div key={index} className="flex gap-3 items-start p-3 bg-orange-50 border border-orange-100 rounded-lg">
                        <span className="text-orange-600 font-bold text-lg flex-shrink-0">•</span>
                        <p className="text-sm text-slate-700 font-medium">{topicName}</p>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex gap-3 items-start p-3 bg-orange-50 border border-orange-100 rounded-lg">
                    <span className="text-orange-600 font-bold text-lg flex-shrink-0">•</span>
                    <p className="text-sm text-slate-700 font-medium">Introduction to Concepts</p>
                  </div>
                </div>
              )}
            </ContentCard>

            <ContentCard title="Technical Glossary" icon={<Book className="text-blue-500" />}>
              {results && results.sections && results.sections.key_terms ? (
                <div className="space-y-3">
                  {results.sections.key_terms.split('\n').filter(line => line.trim()).map((term, index) => {
                    const match = term.match(/^-\s*\*\*(.+?)\*\*:\s*(.+)$/);
                    if (match) {
                      return (
                        <div key={index} className="p-3 bg-blue-50 border border-blue-100 rounded-lg">
                          <p className="text-sm">
                            <span className="font-semibold text-blue-900">{match[1]}</span>
                            <span className="text-slate-700">: {match[2]}</span>
                          </p>
                        </div>
                      );
                    }
                    return (
                      <span key={index} className="text-xs bg-blue-50 text-blue-700 px-3 py-1.5 rounded-full border border-blue-100 inline-block">
                        {term.replace(/^-\s*/, '')}
                      </span>
                    );
                  })}
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded-full border border-blue-100">NLP [cite: 22]</span>
                  <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded-full border border-blue-100">Whisper [cite: 37]</span>
                </div>
              )}
            </ContentCard>

            <ContentCard title="Keyword Cloud" icon={<Cloud className="text-cyan-500" />}>
              {results && results.sections && results.sections.keywords ? (
                <div className="flex flex-wrap gap-2">
                  {results.sections.keywords.split(',').map((keyword, index) => (
                    <span 
                      key={index} 
                      className="text-xs bg-cyan-50 text-cyan-700 px-3 py-1.5 rounded-full border border-cyan-100 hover:bg-cyan-100 transition"
                    >
                      {keyword.trim()}
                    </span>
                  ))}
                </div>
              ) : (
                <div className="h-32 flex items-center justify-center bg-slate-50 rounded-lg border border-slate-100">
                  <span className="text-slate-400 text-xs">Visual word cloud generation [cite: 27]</span>
                </div>
              )}
            </ContentCard>
          </div>
        </div>
      </main>
    </div>
  );
}

// Reusable Card Component
function ContentCard({ title, icon, children, badge }) {
  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-6">
        <div className="flex items-center gap-3">
          {icon}
          <h3 className="font-bold text-lg text-slate-800">{title}</h3>
        </div>
        {badge && <span className="text-[10px] uppercase tracking-widest font-bold bg-slate-100 px-2 py-1 rounded text-slate-500">{badge}</span>}
      </div>
      {children}
    </div>
  );
}

// Quiz Section Component with Interactive MCQ
function QuizSection({ quizData, quizAnswers, quizSubmitted, quizResults, onOptionSelect, onSubmitQuiz, onResetQuiz }) {
  // Parse quiz data
  const questions = [];
  const questionBlocks = quizData.split('\n\n').filter(q => q.trim());
  
  questionBlocks.forEach((block, blockIndex) => {
    const lines = block.split('\n').filter(line => line.trim());
    const questionText = lines.find(line => line.match(/^Q\d+\./));
    const answerLine = lines.find(line => line.toLowerCase().includes('**answer:**'));
    const options = lines.filter(line => line.match(/^[A-D]\)/));
    
    if (questionText && options.length > 0) {
      // Find correct answer index
      let correctIndex = -1;
      if (answerLine) {
        const answerMatch = answerLine.match(/\*\*Answer:\*\*\s*([A-D])\)/i);
        if (answerMatch) {
          const correctLetter = answerMatch[1].toUpperCase();
          correctIndex = correctLetter.charCodeAt(0) - 65; // A=0, B=1, C=2, D=3
        }
      }
      
      questions.push({
        index: blockIndex,
        question: questionText,
        options: options,
        correctAnswer: correctIndex,
        fullAnswer: answerLine
      });
    }
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-3">
        <p className="text-slate-500 italic text-sm">Test your understanding with auto-generated MCQs</p>
        <div className="flex gap-2">
          {!quizSubmitted ? (
            <button
              onClick={onSubmitQuiz}
              className="px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 transition"
            >
              Submit Quiz
            </button>
          ) : (
            <button
              onClick={onResetQuiz}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition"
            >
              Retry Quiz
            </button>
          )}
        </div>
      </div>

      {questions.map((q, qIndex) => {
        const selectedOption = quizAnswers[q.index];
        const result = quizResults[q.index];
        
        return (
          <div key={q.index} className="p-4 bg-purple-50 border border-purple-100 rounded-lg">
            <p className="text-slate-800 font-semibold mb-3">{q.question}</p>
            <div className="space-y-2 ml-2">
              {q.options.map((option, optIndex) => {
                let optionClass = "p-2 rounded-lg border transition cursor-pointer ";
                
                if (!quizSubmitted) {
                  // Before submission
                  optionClass += selectedOption === optIndex 
                    ? "bg-purple-200 border-purple-400 border-2" 
                    : "bg-white border-purple-200 hover:bg-purple-100";
                } else {
                  // After submission
                  if (optIndex === q.correctAnswer) {
                    optionClass += "bg-green-200 border-green-500 border-2"; // Correct answer
                  } else if (selectedOption === optIndex && optIndex !== q.correctAnswer) {
                    optionClass += "bg-red-200 border-red-500 border-2"; // Wrong selection
                  } else {
                    optionClass += "bg-white border-purple-200 opacity-50";
                  }
                }
                
                return (
                  <div
                    key={optIndex}
                    className={optionClass}
                    onClick={() => onOptionSelect(q.index, optIndex)}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-700">{option}</span>
                      {quizSubmitted && optIndex === q.correctAnswer && (
                        <CheckCircle size={16} className="text-green-600" />
                      )}
                      {quizSubmitted && selectedOption === optIndex && optIndex !== q.correctAnswer && (
                        <XCircle size={16} className="text-red-600" />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            
            {quizSubmitted && result && (
              <div className={`mt-3 p-2 rounded-lg ${result.isCorrect ? 'bg-green-100' : 'bg-amber-100'}`}>
                <p className={`text-sm font-medium ${result.isCorrect ? 'text-green-700' : 'text-amber-700'}`}>
                  {result.isCorrect ? '✓ Correct!' : `✗ Incorrect. Correct answer: ${q.fullAnswer?.replace(/\*\*/g, '')}`}
                </p>
              </div>
            )}
          </div>
        );
      })}
      
      {quizSubmitted && (
        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg text-center">
          <p className="text-blue-800 font-semibold">
            Quiz Complete! You scored {Object.values(quizResults).filter(r => r.isCorrect).length} out of {questions.length}
          </p>
        </div>
      )}
    </div>
  );
}

export default App;
