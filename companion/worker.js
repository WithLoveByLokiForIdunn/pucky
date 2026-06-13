// Cloudflare Worker — Claude companion proxy
// Deploy at: cloudflare.com → Workers & Pages → Create Worker
//
// Secrets to set in Worker Settings → Variables:
//   ANTHROPIC_API_KEY  — your Anthropic key
//   ACCESS_TOKEN       — any password you choose (used by the phone app)

export default {
  async fetch(request, env) {
    const cors = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: cors });
    }

    if (request.method !== 'POST') {
      return new Response('Not found', { status: 404, headers: cors });
    }

    const auth = request.headers.get('Authorization') || '';
    if (env.ACCESS_TOKEN && auth !== `Bearer ${env.ACCESS_TOKEN}`) {
      return new Response('Unauthorized', { status: 401, headers: cors });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return new Response('Bad request', { status: 400, headers: cors });
    }

    const upstream = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model:      body.model      || 'claude-sonnet-4-6',
        max_tokens: body.max_tokens || 400,
        system:     body.system,
        messages:   body.messages,
      }),
    });

    const data = await upstream.json();

    return new Response(JSON.stringify(data), {
      headers: { 'Content-Type': 'application/json', ...cors },
    });
  },
};
