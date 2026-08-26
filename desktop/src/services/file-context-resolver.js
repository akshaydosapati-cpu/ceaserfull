const fs = require("fs")
const path = require("path")
const crypto = require("crypto")

const PROTECTED = /(^|[\\/])(?:\.env(?:\..*)?|credentials?|.*(?:private|secret)[-_]?key.*|id_rsa|id_ed25519)(?:$|[\\/])/i
const MEDIA = new Set([".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".webm", ".m4v"])
const DOCUMENTS = new Set([".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".md", ".csv", ".xls", ".xlsx", ".js", ".ts", ".jsx", ".tsx", ".py", ".json", ".css", ".html"])
const SUPPORTED = new Set([...MEDIA, ...DOCUMENTS])
const SOURCES = new Set(["chat_attachment", "file_picker", "attachment", "explicit_path", "selected_file", "recent_context"])

class FileContextResolver {
  constructor({ deviceId, maxBytes = 100 * 1024 * 1024 } = {}) { this.deviceId=deviceId; this.maxBytes=maxBytes; this.references=new Map(); this.activeReference=null }
  register(candidate = {}) {
    const localPath=path.resolve(String(candidate.local_path||candidate.path||"")); if(!localPath||!fs.existsSync(localPath)||!fs.statSync(localPath).isFile())return null
    if(PROTECTED.test(localPath)||!SUPPORTED.has(path.extname(localPath).toLowerCase())||fs.statSync(localPath).size>this.maxBytes)return null
    const source=SOURCES.has(candidate.source)?candidate.source:"explicit_path";const id=String(candidate.file_reference||crypto.randomUUID()); const value={file_reference:id,filename:path.basename(localPath),local_path:localPath,mime_type:candidate.mime_type||this.mime(localPath),size:fs.statSync(localPath).size,device_id:this.deviceId,source,fingerprint:this.fingerprint(localPath)}
    this.references.set(id,value);this.activeReference=id;return value
  }
  resolve(args={}) {
    const explicit=args.file_reference&&this.references.get(String(args.file_reference)); if(explicit)return explicit
    for(const candidate of args.attachments||[]) { const found=this.register({...candidate,source:"attachment"});if(found)return found }
    if(args.explicit_path) { const found=this.register({local_path:args.explicit_path,source:"explicit_path"});if(found)return found }
    if(args.active_file_reference&&this.references.has(args.active_file_reference))return this.references.get(args.active_file_reference)
    return {status:"clarification_required",error_code:"file_context_required",message:"Which image or video would you like me to post?"}
  }
  mime(file){return({".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".webp":"image/webp",".gif":"image/gif",".mp4":"video/mp4",".mov":"video/quicktime",".webm":"video/webm",".m4v":"video/x-m4v"})[path.extname(file).toLowerCase()]||"application/octet-stream"}
  fingerprint(file){const stat=fs.statSync(file);return crypto.createHash("sha256").update(`${path.basename(file)}|${stat.size}|${stat.mtimeMs}`).digest("hex")}
}
function browserUploadArguments(context,target){if(!context?.local_path||!context?.file_reference)throw new Error("invalid_file_context");return{file_context:{file_reference:context.file_reference},file_path:context.local_path,authorized_roots:[path.dirname(context.local_path)],asset_fingerprint:context.fingerprint,file_reference:context.file_reference,target}}
module.exports={FileContextResolver,PROTECTED,MEDIA,DOCUMENTS,SUPPORTED,browserUploadArguments}
