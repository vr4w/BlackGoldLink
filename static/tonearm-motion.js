// Identical hardware, rotated 180 degrees between the two records.
// The first pivot is outside the upper LEFT edge; the second outside lower RIGHT.
export const ARM_LENGTH=2.35;
export const RECORD_ANGULAR_SPEED=(33+1/3)*2*Math.PI/60;
export const PIVOT_X=2.08;
export const PIVOT_Z=-1.06;
export function tonearmPivot(mount){return {x:-mount*PIVOT_X,z:mount*PIVOT_Z};}
export function needlePoint(mount,depth){
 const bounded=Math.max(0,Math.min(1,depth));
 const radius=1.695*(.975-.63*bounded);
 const pivot=tonearmPivot(mount);
 const distance=Math.hypot(pivot.x,pivot.z);
 const along=(radius*radius-ARM_LENGTH*ARM_LENGTH+distance*distance)/(2*distance);
 const height=Math.sqrt(Math.max(0,radius*radius-along*along));
 return {x:along*pivot.x/distance-height*pivot.z/distance,z:along*pivot.z/distance+height*pivot.x/distance,radius};
}
