import { ThinkPixelSRClient } from "../src/index.js";
const baseUrl = process.env.THINKPIXEL_BASE_URL;
if (!baseUrl)
    throw new Error("THINKPIXEL_BASE_URL is required");
const client = new ThinkPixelSRClient({ baseUrl });
const result = await client.search("synthetic document", { language: "en" });
console.log("Search hits:", result.results.length);
