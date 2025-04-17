const express=require("express");
const jwt=require("jsonwebtoken");

const auth=(req,res,next)=>{
    try {
        const token=req.header("x-auth-token");

        if(!token) return res.status(400).json({msg:"Invalid token"});
    
        const verified=jwt.verify(token,"passwordkey");
    
        if(!verified) return res.status(400).json({msg:"not a verified user"});
    
        req.user=verified.id;
        req.token=token;
        next();
        
    } catch (err) {

        res.status(500).json({error:err.message});
        
    }

   

}

module.exports=auth;