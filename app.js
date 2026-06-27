document.addEventListener('DOMContentLoaded', function(){
  const videoInput = document.getElementById('video_url');
  const thumb = document.getElementById('thumb');
  const metaTitle = document.getElementById('meta-title');
  const metaAuthor = document.getElementById('meta-author');
  const watchLink = document.getElementById('watch-link');

  async function fetchMetadata(){
    const v = videoInput.value.trim();
    if(!v) return;
    const res = await fetch('/api/metadata', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({video_url: v})});
    if(res.ok){
      const j = await res.json();
      thumb.src = j.thumbnail;
      metaTitle.textContent = j.title || 'Video title';
      metaAuthor.textContent = j.author || '';
      watchLink.href = j.watch_url || '#';
    }
  }

  videoInput.addEventListener('blur', fetchMetadata);

  // Chat
  const chatBtn = document.getElementById('chat-btn');
  const chatInput = document.getElementById('chat-input');
  const chatResp = document.getElementById('chat-response');
  chatBtn.addEventListener('click', async ()=>{
    const q = chatInput.value.trim();
    const v = videoInput.value.trim();
    if(!q || !v) return;
    chatResp.textContent = 'Thinking...';
    const res = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({video_url: v, question: q})});
    const j = await res.json();
    chatResp.textContent = j.answer || j.error || 'No answer';
  });

  // Quiz
  document.getElementById('quiz-btn').addEventListener('click', async ()=>{
    const v = videoInput.value.trim();
    if(!v) return;
    const area = document.getElementById('quiz-area');
    area.textContent = 'Generating quiz...';
    const res = await fetch('/api/quiz', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({video_url: v})});
    const j = await res.json();
    if(j.questions){
      area.innerHTML = '';
      j.questions.forEach((q,i)=>{
        const div = document.createElement('div');
        div.className = 'mb-3';
        div.innerHTML = `<strong>Q${i+1}.</strong> ${q.question}<br>` + q.options.map(o=>`<button class="btn btn-sm btn-outline-secondary m-1" onclick="alert('Answer: ${q.answer}')">${o}</button>`).join('');
        area.appendChild(div);
      });
    } else {
      area.textContent = j.error || 'No quiz generated';
    }
  });

  // Translate
  document.getElementById('translate-btn').addEventListener('click', async ()=>{
    const target = document.getElementById('translate-target').value;
    const summaryPre = document.querySelector('pre');
    if(!summaryPre) return alert('No summary to translate');
    const text = summaryPre.textContent;
    const res = await fetch('/api/translate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text, target})});
    const j = await res.json();
    if(j.translated){
      summaryPre.textContent = j.translated;
    } else {
      alert(j.error || 'Translation failed');
    }
  });

});
