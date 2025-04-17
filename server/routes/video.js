const express = require("express");
const multer = require("multer");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const auth=require("../middlewares/userMiddleware");
const User = require("../models/usermodel");

const router = express.Router();

// Configure multer for file upload
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, "uploads/");
  },
  filename: function (req, file, cb) {
    cb(null, Date.now() + "_" + file.originalname);
  }
});
const upload = multer({ storage });

// POST /api/video/summarize
router.post("/summarize", auth ,upload.single("video"), async (req, res) => {
    const videoPath = req.file.path;
    const pdfName = `${Date.now()}_${req.body.pdfName || "summary"}.pdf`;
  
    const pythonProcess = spawn("python", ["newserver.py", videoPath, pdfName]);
  
    let stdoutData = "";
    let errorLog = "";
  
    pythonProcess.stdout.on("data", (data) => {
      stdoutData += data.toString();
    });
  
    pythonProcess.stderr.on("data", (data) => {
      errorLog += data.toString();
      console.error("[Python Error]", data.toString());
    });
  
    pythonProcess.on("close", async (code) => {
      fs.unlink(videoPath, () => {}); // Clean up uploaded video
  
      try {
        const result = JSON.parse(stdoutData);
        if (result.success) {

          const user=await User.findById(req.user);
          user.pdfs.push(result.url);
          await user.save();

          return res.json({ success: true, pdfURL: result.url });
        } else {
          return res.status(500).json({
            success: false,
            error: result.error || "Video summarization failed",
            details: result.details || errorLog
          });
        }
      } catch (err) {
        return res.status(500).json({
          success: false,
          error: "Failed to parse response from Python script.",
          details: stdoutData || errorLog || err.message
        });
      }
    });
  });
  

module.exports = router;
