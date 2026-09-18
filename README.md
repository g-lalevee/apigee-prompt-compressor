# Prompt Compression Gateway for Apigee X

[![PyPI status](https://img.shields.io/pypi/status/ansicolortags.svg)](https://pypi.python.org/pypi/ansicolortags/) 

**This is not an official Google product.**<BR>This implementation is not an official Google product, nor is it part of an official Google product. Support is available on a best-effort basis via GitHub.

***

This repository provides a complete blueprint for deploying an **AI-powered Prompt Compression image** on Google Cloud Run and integrating it via an **Apigee SharedFlow**.

By compressing prompts at the edge, you can:
*   **Reduce LLM Costs**: Save up to 70% on token usage.
*   **Improve Latency**: Smaller prompts result in faster LLM generation times.
*   **Optimize Context**: Fit more information into limited LLM context windows.

---

## 🏗️ Origin & Credits

This project is an custom optimized version of the [prompt-compression-gateway](https://github.com/Kelpejol/prompt-compression-gateway) by Kelpejol.

The original implementation was enhanced with:
*   Cloud Run serverless deployment compatibility.
*   Apigee X SharedFlow integration and GCP security.
*   Production-grade caching and model pre-loading.
*   LLMLingua-2 Token Classification for faster inference.

---


## ✨ Optimizations Included

### **Container & Cold-Start Optimizations**
*   **Pre-baked Model Weights**: BERT model weights (~711MB) are baked into `/app/model_cache` during Docker build, eliminating runtime Hugging Face WAN downloads and slashing cold boot from ~52s down to ~2.5s.
*   **Air-Gapped Offline Mode**: `TRANSFORMERS_OFFLINE=1` and `HF_HUB_OFFLINE=1` guarantee zero external DNS or HTTP calls on startup.
*   **CPU-Only PyTorch**: Installs PyTorch via `--index-url https://download.pytorch.org/whl/cpu`, purging ~2.5GB of unused CUDA binaries and shrinking image size by ~70%.
*   **Bytecode Pre-compilation**: Python bytecode compiled ahead of time (`compileall -b`) for fast import execution.

### **Hot-Path & Concurrency Optimizations**
*   **Threadpool Offloading**: Synchronous route handler dispatches CPU-bound PyTorch inference to AnyIO worker threadpool, keeping the ASGI event loop responsive for `/health` probes.
*   **Multi-Worker Execution**: Uvicorn runs 2 worker processes with PyTorch CPU thread tuning (`torch.set_num_threads(2)` and `inference_mode()`) to utilize all 4 vCPUs without GIL lockup.
*   **Full-Response TTL In-Memory Cache**: Caches full response payloads for 5,000 items, bypassing tokenization and inference completely for cache hits in **<2ms**.
*   **Fast Tokenization**: Uses `tiktoken.encode_ordinary()` for high-throughput policy verification.

---

## 📂 Repository Structure

*   **`/compressor_image`**: The FastAPI application (LLMLingua-2 + Caching).
*   **`/apigee`**: Prompt Compressor SharedFlow bundle source code and zip file.
*   **`Dockerfile`**: Production-optimized for Google Cloud Run.
*   **`tests/`**: Automated test suite for models, policies, and caching.

---

## 🚀 1. Deploy the Cloud Run Gateway

### Prerequisites
*   Google Cloud Project with billing enabled.
*   `gcloud` CLI installed.

### Deployment Commands
```bash
# 1. Build and Push Image (from root)
gcloud builds submit --tag europe-west1-docker.pkg.dev/$(gcloud config get-value project)/prompt-compression-repo/gateway:v13 .

# 2. Deploy to Cloud Run
gcloud run deploy prompt-compression-gateway \
    --image europe-west1-docker.pkg.dev/$(gcloud config get-value project)/prompt-compression-repo/gateway:v13 \
    --platform managed \
    --region europe-west1 \
    --no-allow-unauthenticated \
    --memory 8Gi \
    --cpu 4 \
    --cpu-boost \
    --concurrency 15 \
    --timeout 900 \
    --min-instances 0
```

#### Option B: Configure via the Google Cloud Console
1. Go to the **Cloud Run** console in Google Cloud.
2. Select your service **`prompt-compression-gateway`**.
3. Click **Edit & Deploy New Revision** at the top.
4. Expand the **Container, variables, networking, security** section if needed.
5. Under the **Scaling** tab, set **Minimum number of instances** to `1`.
6. Click **Deploy**.

---

## 🔐 2. Security Configuration

Allow Apigee to call the protected service:

```bash
# 1. Create Service Account
gcloud iam service-accounts create apigee-run-invoker

# 2. Grant Invoker Role
gcloud run services add-iam-policy-binding prompt-compression-gateway \
    --member="serviceAccount:apigee-run-invoker@$(gcloud config get-value project).iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region europe-west1
```

---

## 🛠️ 3. Apigee Integration Pattern

The recommended way to use this gateway is by deploying the provided **SharedFlow** and calling it from your API Proxy.

### Step A: Deploy the SharedFlow
1. Navigate to the `/apigee` directory.
2. Zip the `sharedflowbundle` folder: `zip -r promptCompressor.zip sharedflowbundle`.
3. Import and deploy the `promptCompressor.zip` into your Apigee environment.

### Step B: Extract the Original Prompt
In your API Proxy, before calling the SharedFlow, extract the prompt text from your request.

```xml
<ExtractVariables name="EV-getOriginalPrompt">
  <Source>request</Source>
  <JSONPayload>
    <Variable name="originalPrompt">
      <JSONPath>$.messages[0].content[0].text</JSONPath>
    </Variable>
  </JSONPayload>
</ExtractVariables>
```

### Step C: Call the SharedFlow
Attach a `FlowCallout` policy to trigger the compression. The SharedFlow handles the authentication and the call to Cloud Run.

### Step D: Update the Request Payload
After the SharedFlow returns, use this JavaScript to inject the compressed text back into your original payload (create a Javasctipt policy to use this source code).

```javascript
var originalPayload = JSON.parse(context.getVariable("request.content"));
var compressedText = context.getVariable("compression.compressedPrompt");

if (originalPayload.messages && originalPayload.messages[0].content[0]) {
    originalPayload.messages[0].content[0].text = compressedText;
}

context.setVariable("request.content", JSON.stringify(originalPayload));
```

---

## 🔍 Debugging & Tracing

After the SharedFlow executes, you can use the **Apigee Trace Tool** to inspect the compression efficiency. The SharedFlow populates a set of flow variables prefixed with `compression.*`.

### **Efficiency Variables**
| Variable | Description |
| :--- | :--- |
| `compression.originalPrompt` | The raw prompt text before compression. |
| `compression.originalTokens` | Token count of the original prompt. |
| `compression.compressedPrompt` | The final prompt text after AI compression. |
| `compression.compressedTokens` | Token count after compression. |

### **Example Trace Result**


| Variable | Value |
| :--- | :--- |
| `compression.originalPrompt` | *"Great. And finally, someone needs to write the email to the users. Just a short one, you know? like Hey, we have a new site. That kind of thing."* |
| `compression.originalTokens` | `37`|
| `compression.compressedPrompt` | *"Great. finally someone needs write email to users. short one? new site. thing."* |
| `compression.compressedTokens` | `18` (50% reduction!) |