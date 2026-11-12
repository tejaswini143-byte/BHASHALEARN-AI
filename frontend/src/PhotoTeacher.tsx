import{useEffect,useMemo}from"react";import*as THREE from"three";import type{TeacherMode}from"./teacherCore";import type{TeacherPhotoAsset}from"./teacherPhoto";
/** Flat, browser-local image presentation; this does not create a rigged avatar. */
export function PhotoTeacher({photo,mode}:{photo:TeacherPhotoAsset;mode:TeacherMode}){
 const texture=useMemo(()=>new THREE.CanvasTexture(photo.bitmap),[photo.bitmap]);
 useEffect(()=>{texture.colorSpace=THREE.SRGBColorSpace;texture.needsUpdate=true;return()=>texture.dispose()},[texture]);
 const aspect=photo.width/photo.height,height=Math.min(2.8,2.1/aspect),width=height*aspect,holo=mode==="holographic";
 return <group position={[-2,height/2+0.08,-0.5]}><mesh><planeGeometry args={[width,height]}/><meshBasicMaterial map={texture} color={holo?"#9ceeff":"#fff"} transparent opacity={holo?0.84:1} side={THREE.DoubleSide} toneMapped={false}/></mesh>{holo&&<mesh position={[0,0,0.008]}><planeGeometry args={[width,height]}/><meshBasicMaterial color="#62ddff" wireframe transparent opacity={0.16} depthWrite={false} side={THREE.DoubleSide}/></mesh>}</group>
}
