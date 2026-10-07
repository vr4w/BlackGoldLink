"""Entirely fictional fixtures. Never saved in the real user database."""
def profiles():
    titles=['After Hours','Signal From The Loft','Soft Circuits','Northbound','Blue Room Session','Echoes In Concrete','Low Orbit','Side B Stories','Silent Harbour','Warm Static','Night Bus','Loose Ends']
    names=['The Paper Satellites','Lowlight Assembly','Analog District','Midnight Workshop']
    releases=[dict(id=-(i+1),title=title,year=1988+i,artists=[dict(id=-(i%4+1),name=names[i%4])],genres=['Electronic' if i%2 else 'Jazz'],formats=[{'name':'Vinyl','qty':'1','descriptions':['LP']}],styles=[],cover=f'demo-covers/{i+1:02}.svg',master_id=0,labels=[]) for i,title in enumerate(titles)]
    return ({'collection':releases[:8],'wantlist':releases[8:11]}, {'collection':releases[2:11],'wantlist':releases[:2]+releases[11:]})
