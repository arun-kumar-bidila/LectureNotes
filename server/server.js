const express=require("express");
const mongoose=require("mongoose");
const userRouter = require("./routes/user");
const router = require("./routes/video");
require("dotenv").config();


const port = process.env.PORT || 3000;

const app=express();

app.use(express.json());
app.use(userRouter);
app.use(router);

mongoose.connect(process.env.MONGO_URI,{useNewUrlParser:true,useUnifiedTopology:true}).then(()=>{
    console.log("Database connection successful")
}).catch((e)=>{
    console.log("Error in database connection")
});

app.listen(port,"0.0.0.0",()=>{
    console.log(`Server started at port ${port}`);
});