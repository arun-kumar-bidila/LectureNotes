const express=require("express");
const bcryptjs=require("bcryptjs");
const jwt=require("jsonwebtoken");
const User=require("../models/usermodel");
const auth = require("../middlewares/userMiddleware");

const userRouter=express.Router();

userRouter.post("/api/signup", async (req,res)=>{

    try {
        const {email,password}=req.body;

    const existingUser=await User.findOne({email});

    if(existingUser){
        return res.status(400).json({msg:"Email already exists"});
    }

    const hashedPassword=await bcryptjs.hash(password,8);

    let newUser=new User({
        email:email,
        password:hashedPassword
    });

    newUser=await newUser.save();

    res.status(200).json(newUser);
        
    } catch (e) {
        res.status(500).json({error:e.message})
        
    }

    

});

userRouter.post("/api/signin", async (req,res)=>{

    try {
        const {email,password}=req.body;

        const user=await User.findOne({email});
        if(!user) return res.status(400).json({msg:"User doesnt exist"});
    
        const isMatch=await bcryptjs.compare(password,user.password);
    
        if(!isMatch) return res.status(400).json({msg:"email and password doesnt match"});
    
        const token=jwt.sign({id:user._id},"passwordkey",{expiresIn:"1h"})
    
        res.status(200).json({msg:"Login successful",token,...user._doc});
        
    } catch (err) {
        res.status(500).json({error:err.message});
        
    }

   

});


userRouter.post("/tokenIsValid",async(req,res)=>{

    try {
        const token=req.header("x-auth-token");

        if(!token) return res.json(false);
    
        const verified=await jwt.verify(token,"passwordkey");
    
        if(!verified) return res.json(false);
    
        const user=await User.findById(verified.id);
    
        if(!user) return res.json(false);
    
        res.json(true);
        
    } catch (err) {
        res.status(500).json({error:err.message});

        
    }

   


});


userRouter.get("/",auth,async (req,res)=>{

    try {

        const user=await User.findById(req.user);
        console.log(req.token);

        return res.json({token:req.token,...user._doc});
        
        
    } catch (err) {
        return res.status(500).json({error:err.message});
        
    }

});

module.exports=userRouter;