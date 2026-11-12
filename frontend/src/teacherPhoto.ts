export const MAX_TEACHER_PHOTO_BYTES=8*1024*1024;
export type TeacherPhotoAsset={name:string;width:number;height:number;bitmap:ImageBitmap;previewUrl:string};
type PhotoFile=File;
type Options={decode?:(file:Blob)=>Promise<ImageBitmap>;createObjectURL?:(file:Blob)=>string};
function sniff(b:Uint8Array):string|null{const h=Array.from(b.slice(0,8),x=>x.toString(16).padStart(2,"0")).join("");if(h.startsWith("89504e470d0a1a0a"))return"image/png";if(h.startsWith("ffd8ff"))return"image/jpeg";if(b.length>=12&&String.fromCharCode(...b.slice(0,4))==="RIFF"&&String.fromCharCode(...b.slice(8,12))==="WEBP")return"image/webp";return null}
export async function loadTeacherPhoto(file:PhotoFile,permission:boolean,options:Options={}):Promise<TeacherPhotoAsset>{
 if(!permission)throw Error("Confirm you have permission to use this person's likeness.");
 if(!file.size||file.size>MAX_TEACHER_PHOTO_BYTES)throw Error("Choose a non-empty image smaller than 8 MB.");
 if(!["image/png","image/jpeg","image/webp"].includes(file.type))throw Error("Choose a PNG, JPEG, or WebP image.");
 if(sniff(new Uint8Array(await file.arrayBuffer()))!==file.type)throw Error("The selected file does not match its PNG, JPEG, or WebP format.");
 let bitmap:ImageBitmap;try{bitmap=await (options.decode ?? (f=>createImageBitmap(f)))(file)}catch{throw Error("This image could not be decoded. Choose another PNG, JPEG, or WebP file.")}
 if(!bitmap.width||!bitmap.height||bitmap.width*bitmap.height>40_000_000){bitmap.close();throw Error("The image dimensions are unsupported or too large to preview.")}
 let previewUrl:string;try{previewUrl=(options.createObjectURL ?? (f=>URL.createObjectURL(f)))(file)}catch{bitmap.close();throw Error("The image preview could not be created.")}
 return{name:file.name,width:bitmap.width,height:bitmap.height,bitmap,previewUrl}
}
export function disposeTeacherPhoto(photo:TeacherPhotoAsset,revoke:(url:string)=>void=url=>URL.revokeObjectURL(url)):void{photo.bitmap.close();revoke(photo.previewUrl)}
