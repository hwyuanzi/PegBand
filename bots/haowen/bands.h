#ifndef HAOWEN_PEGBAND_BANDS_H
#define HAOWEN_PEGBAND_BANDS_H

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <limits>
#include <numeric>
#include <random>
#include <unordered_set>
#include <vector>

namespace pegband {

using Hull = std::vector<int>;
using Bits = std::vector<uint64_t>;
struct BandPlan { std::vector<Hull> bands; int score = 0; };

namespace band_detail {
struct Point { int x, y, square; };
inline int cross(const Point& a, const Point& b, const Point& c) {
    return (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
}
inline bool on_segment(const Point& p, const Point& a, const Point& b) {
    return cross(a,b,p)==0 && std::min(a.x,b.x)<=p.x && p.x<=std::max(a.x,b.x)
        && std::min(a.y,b.y)<=p.y && p.y<=std::max(a.y,b.y);
}
inline std::vector<Point> convex_hull(int n, const Hull& ids) {
    std::vector<Point> p;
    for (int id: ids) p.push_back({id%n,id/n,id});
    std::sort(p.begin(),p.end(),[](const Point& a,const Point& b){
        return a.x!=b.x ? a.x<b.x : a.y<b.y;
    });
    p.erase(std::unique(p.begin(),p.end(),[](const Point&a,const Point&b){return a.square==b.square;}),p.end());
    if(p.size()<3) return p;
    std::vector<Point> h;
    for(const Point& q:p) {
        while(h.size()>=2 && cross(h[h.size()-2],h.back(),q)<=0)h.pop_back();
        h.push_back(q);
    }
    size_t lower=h.size();
    for(int i=(int)p.size()-2;i>=0;--i) {
        while(h.size()>lower && cross(h[h.size()-2],h.back(),p[i])<=0)h.pop_back();
        h.push_back(p[i]);
    }
    h.pop_back();
    return h;
}
inline bool contains(const std::vector<Point>& h,const Point& p) {
    if(h.empty()) return false;
    if(h.size()==1) return h[0].square==p.square;
    if(h.size()==2) return on_segment(p,h[0],h[1]);
    for(size_t i=0;i<h.size();++i)
        if(cross(h[i],h[(i+1)%h.size()],p)<0)return false;
    return true;
}

// Exact Liang--Barsky clipping in doubled coordinates. A corner-only touch
// has equal interval endpoints and therefore contributes no scored square.
inline bool segment_hits_cell(const Point& a,const Point& b,int x,int y) {
    int dx=2*(b.x-a.x),dy=2*(b.y-a.y);
    int t0n=0,t0d=1,t1n=1,t1d=1;
    int ps[4]={-dx,dx,-dy,dy};
    int qs[4]={2*a.x-(2*x-1),(2*x+1)-2*a.x,2*a.y-(2*y-1),(2*y+1)-2*a.y};
    for(int z=0;z<4;++z) {
        int p=ps[z],q=qs[z];
        if(p==0) { if(q<0)return false; continue; }
        if(p<0) {
            int num=-q,den=-p;
            if(num*t0d>t0n*den){t0n=num;t0d=den;}
        } else if(q*t1d<t1n*p){t1n=q;t1d=p;}
        if(t0n*t1d>t1n*t0d)return false;
    }
    return t0n*t1d<t1n*t0d;
}
inline int count(const Bits& a) {
    int v=0;for(uint64_t x:a)v+=__builtin_popcountll(x);return v;
}
inline int gain(const Bits& a,const Bits& covered) {
    int v=0;for(size_t w=0;w<a.size();++w)v+=__builtin_popcountll(a[w]&~covered[w]);return v;
}
inline void unite(Bits& a,const Bits& b) {
    for(size_t w=0;w<a.size();++w)a[w]|=b[w];
}
inline bool subset(const Bits& a,const Bits& b) {
    for(size_t w=0;w<a.size();++w)if(a[w]&~b[w])return false;
    return true;
}
inline int floor_div(int a,int b) {
    int q=a/b,r=a%b;
    return q-(r<0);
}
inline void set_range(Bits& bits,int lo,int hi) {
    if(lo>hi)return;
    int first=lo>>6,last=hi>>6;
    uint64_t low=~uint64_t(0)<<(lo&63),high=~uint64_t(0)>>(63-(hi&63));
    if(first==last)bits[first]|=low&high;
    else {
        bits[first]|=low;
        for(int w=first+1;w<last;++w)bits[w]=~uint64_t(0);
        bits[last]|=high;
    }
}
inline Bits left_halfplane(int n,const Point& a,const Point& b) {
    Bits bits((n*n+63)/64,0);
    int dx=b.x-a.x,dy=b.y-a.y;
    for(int y=0;y<n;++y) {
        int lo=0,hi=n-1,v=dx*(y-a.y)+dy*a.x;
        if(dy>0)hi=std::min(hi,floor_div(v,dy));
        else if(dy<0)lo=std::max(lo,-floor_div(v,-dy));
        else if(v<0)continue;
        if(lo<=hi)set_range(bits,y*n+lo,y*n+hi);
    }
    return bits;
}
inline Bits segment_raster(int n,const Point& a,const Point& b) {
    Bits bits((n*n+63)/64,0);
    if(a.square==b.square) {
        bits[a.square>>6]|=uint64_t(1)<<(a.square&63);
        return bits;
    }
    int minx=std::min(a.x,b.x),maxx=std::max(a.x,b.x);
    int miny=std::min(a.y,b.y),maxy=std::max(a.y,b.y);
    int dx=b.x-a.x,dy=b.y-a.y,norm=std::abs(dx)+std::abs(dy);
    for(int y=miny;y<=maxy;++y) {
        int lo=minx,hi=maxx;
        // The square's projection onto the segment normal has radius
        // (|dx|+|dy|)/2. Strict overlap excludes corner-only contacts.
        int v=2*dx*(y-a.y)+2*dy*a.x;
        for(int sign:{1,-1}) {
            int bound=sign*v+norm,slope=sign*dy;
            if(slope>0)hi=std::min(hi,floor_div(bound-1,2*slope));
            else if(slope<0)lo=std::max(lo,floor_div(-bound,-2*slope)+1);
            else if(bound<=0){hi=-1;break;}
        }
        if(lo<=hi)set_range(bits,y*n+lo,y*n+hi);
    }
    return bits;
}
inline double elapsed(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
}
} // namespace band_detail

inline bool legal(int n,const Hull& ids,const Hull& enemy) {
    if(ids.empty() || n<=0)return false;
    for(int id:ids)if(id<0 || id>=n*n)return false;
    auto h=band_detail::convex_hull(n,ids);
    for(int id:enemy)if(band_detail::contains(h,{id%n,id/n,id}))return false;
    return true;
}

inline Bits coverage(int n,const Hull& ids,const Hull& enemy) {
    using namespace band_detail;
    if(n<=0)return {};
    Bits bits((n*n+63)/64,0);
    if(ids.empty())return bits;
    for(int id:ids)if(id<0 || id>=n*n)return bits;
    auto h=convex_hull(n,ids);
    if(h.size()==1) bits[h[0].square/64]|=uint64_t(1)<<(h[0].square%64);
    else if(h.size()==2)bits=segment_raster(n,h[0],h[1]);
    else {
        // A covered cell either contains part of an edge or its center is
        // inside the hull. Scan rows for each edge instead of clipping every
        // cell against every edge; this also accelerates terminal search.
        Bits inside(bits.size(),~uint64_t(0));
        if(n*n%64)inside.back()=(uint64_t(1)<<(n*n%64))-1;
        for(size_t i=0;i<h.size();++i) {
            Bits edge=segment_raster(n,h[i],h[(i+1)%h.size()]);
            Bits left=left_halfplane(n,h[i],h[(i+1)%h.size()]);
            for(size_t w=0;w<bits.size();++w){bits[w]|=edge[w];inside[w]&=left[w];}
        }
        unite(bits,inside);
    }
    for(int id:enemy)if(id>=0 && id<n*n)bits[id/64]&=~(uint64_t(1)<<(id%64));
    return bits;
}

inline BandPlan solve_bands(int n,const Hull& mine_input,const Hull& enemy,int band_count,double seconds) {
    using namespace band_detail;
    BandPlan result;
    if(n<=0 || mine_input.empty() || band_count<=0)return result;
    const auto started=std::chrono::steady_clock::now();
    const double budget=std::max(0.01,seconds);
    Hull mine=mine_input;
    std::sort(mine.begin(),mine.end());
    mine.erase(std::unique(mine.begin(),mine.end()),mine.end());
    if(mine.size()>20)mine.resize(20);
    // When the full hull is legal it dominates every smaller band, so there
    // is no subset search or maximum-coverage optimization to perform.
    if(legal(n,mine,enemy)) {
        Hull hull;
        for(const Point& p:convex_hull(n,mine))hull.push_back(p.square);
        result.score=count(coverage(n,hull,enemy));
        result.bands.push_back(std::move(hull));
        return result;
    }
    int k=(int)mine.size(),words=(n*n+63)/64;
    std::vector<Point> points;
    for(int id:mine)points.push_back({id%n,id/n,id});
    std::vector<Point> enemies;
    for(int id:enemy)enemies.push_back({id%n,id/n,id});
    std::array<uint32_t,20> bad_pair{};
    std::array<std::array<uint32_t,20>,20> bad_third{};
    for(int i=0;i<k;++i)for(int j=i+1;j<k;++j) {
        for(const Point&e:enemies)if(on_segment(e,points[i],points[j])) {
            bad_pair[i]|=uint32_t(1)<<j;bad_pair[j]|=uint32_t(1)<<i;break;
        }
        for(int z=j+1;z<k;++z) {
            bool bad=false;
            int orientation=cross(points[i],points[j],points[z]);
            for(const Point&e:enemies) {
                if(orientation==0) {
                    bad=on_segment(e,points[i],points[j]) || on_segment(e,points[i],points[z]) || on_segment(e,points[j],points[z]);
                } else {
                    int a=cross(points[i],points[j],e),b=cross(points[j],points[z],e),c=cross(points[z],points[i],e);
                    bad=(a>=0 && b>=0 && c>=0)||(a<=0 && b<=0 && c<=0);
                }
                if(bad)break;
            }
            if(bad) {
                bad_third[i][j]|=uint32_t(1)<<z;bad_third[j][i]|=uint32_t(1)<<z;
                bad_third[i][z]|=uint32_t(1)<<j;bad_third[z][i]|=uint32_t(1)<<j;
                bad_third[j][z]|=uint32_t(1)<<i;bad_third[z][j]|=uint32_t(1)<<i;
            }
        }
    }
    const uint32_t limit=uint32_t(1)<<k,full=limit-1;
    std::vector<unsigned char> valid(limit,0);valid[0]=1;
    for(uint32_t mask=1;mask<limit;++mask) {
        int i=__builtin_ctz(mask);uint32_t rest=mask&(mask-1);
        if(!valid[rest] || (bad_pair[i]&rest))continue;
        bool ok=true;
        for(uint32_t q=rest;q;q&=q-1)if(bad_third[i][__builtin_ctz(q)]&rest){ok=false;break;}
        valid[mask]=ok;
    }
    std::vector<uint32_t> masks;
    for(uint32_t mask=1;mask<limit;++mask)if(valid[mask]) {
        bool maximal=true;
        for(uint32_t absent=full^mask;absent;absent&=absent-1)
            if(valid[mask|(absent&-absent)]){maximal=false;break;}
        if(maximal)masks.push_back(mask);
    }

    // A hull only needs its extreme pegs. Cache exact edge crossing and
    // half-plane cell masks, then build every candidate by bit operations.
    std::vector<Bits> edge(k*k,Bits(words)),left(k*k,Bits(words));
    Bits all(words,~uint64_t(0));
    if((n*n)%64)all.back()=(uint64_t(1)<<((n*n)%64))-1;
    for(int id:enemy)if(id>=0 && id<n*n)all[id/64]&=~(uint64_t(1)<<(id%64));
    for(int i=0;i<k;++i)for(int j=0;j<k;++j)if(i!=j) {
        Bits& e=edge[i*k+j];Bits& l=left[i*k+j];
        l=left_halfplane(n,points[i],points[j]);
        if(i<j)e=segment_raster(n,points[i],points[j]);
        else e=edge[j*k+i];
        for(int w=0;w<words;++w){e[w]&=all[w];l[w]&=all[w];}
    }
    struct Candidate { Hull hull; Bits cover; int size; };
    std::vector<Candidate> cand;
    std::unordered_set<uint32_t> seen_hulls;
    for(uint32_t mask:masks) {
        Hull ids;for(int i=0;i<k;++i)if(mask&(uint32_t(1)<<i))ids.push_back(mine[i]);
        auto h=convex_hull(n,ids);
        std::vector<int> ix;Hull hull;uint32_t hull_mask=0;
        for(const Point&p:h){int i=int(std::lower_bound(mine.begin(),mine.end(),p.square)-mine.begin());ix.push_back(i);hull.push_back(p.square);hull_mask|=uint32_t(1)<<i;}
        if(!seen_hulls.insert(hull_mask).second)continue;
        Bits cover(words,0);
        if(ix.size()==1){int id=mine[ix[0]];cover[id/64]|=uint64_t(1)<<(id%64);}
        else if(ix.size()==2)cover=edge[ix[0]*k+ix[1]];
        else {
            Bits inside=all;
            for(size_t z=0;z<ix.size();++z) {
                int e=ix[z]*k+ix[(z+1)%ix.size()];
                for(int w=0;w<words;++w){cover[w]|=edge[e][w];inside[w]&=left[e][w];}
            }
            unite(cover,inside);
        }
        cand.push_back({std::move(hull),std::move(cover),0});cand.back().size=count(cand.back().cover);
    }
    std::sort(cand.begin(),cand.end(),[](const Candidate&a,const Candidate&b){return a.size>b.size;});
    // Geometry-maximal sets can still have identical/dominated raster covers.
    // This small quadratic pass saves substantially more time in the search.
    if(cand.size()<=3000) {
        std::vector<Candidate> reduced;
        for(auto& c:cand) {
            bool dominated=false;
            for(const auto& a:reduced)if(subset(c.cover,a.cover)){dominated=true;break;}
            if(!dominated)reduced.push_back(std::move(c));
        }
        cand=std::move(reduced);
    }
    if(cand.empty())return result;
    int c=(int)cand.size(),r=std::min(band_count,c);
    Bits possible(words,0);for(const auto&a:cand)unite(possible,a.cover);
    int target=count(possible),best_score=-1;
    std::vector<int> best;
    auto score_selection=[&](const std::vector<int>& selected) {
        Bits cover(words,0);for(int j:selected)unite(cover,cand[j].cover);
        return count(cover);
    };
    auto record=[&](const std::vector<int>& selected,int score) {
        if(score>best_score || (score==best_score && selected.size()<best.size())){best_score=score;best=selected;}
    };
    auto greedy=[&](std::vector<int> selected,int randomness,std::mt19937& rng) {
        Bits covered(words,0);std::vector<unsigned char> used(c,0);
        for(int j:selected){unite(covered,cand[j].cover);used[j]=1;}
        while((int)selected.size()<r) {
            int jbest=-1,gbest=0;double weighted=-1;
            for(int j=0;j<c;++j)if(!used[j]) {
                int g=gain(cand[j].cover,covered);
                double weight=g;
                if(randomness)weight*=1.0+(double(rng()%10001)/10000.0)*randomness/100.0;
                if(weight>weighted && g>0){weighted=weight;gbest=g;jbest=j;}
            }
            if(jbest<0 || gbest==0)break;
            selected.push_back(jbest);used[jbest]=1;unite(covered,cand[jbest].cover);
        }
        return selected;
    };
    auto improve=[&](std::vector<int> selected) {
        int score=score_selection(selected);
        for(int pass=0;pass<8;++pass) {
            bool changed=false;
            for(size_t z=0;z<selected.size();++z) {
                Bits base(words,0);
                for(size_t q=0;q<selected.size();++q)if(q!=z)unite(base,cand[selected[q]].cover);
                int base_score=count(base),jb=selected[z],value=score;
                for(int j=0;j<c;++j) {
                    int v=base_score+gain(cand[j].cover,base);
                    if(v>value){value=v;jb=j;}
                }
                if(value>score){selected[z]=jb;score=value;changed=true;}
            }
            if(!changed || score==target || elapsed(started)>budget*0.93)break;
        }
        record(selected,score);
        return selected;
    };
    std::mt19937 rng(0x70656762U+uint32_t(n*31+k*17+band_count));
    improve(greedy({},0,rng));
    if(r==1 || best_score==target) {
        for(int j:best)result.bands.push_back(cand[j].hull);result.score=best_score;return result;
    }
    // Exhaustive pairs are cheap and make the two-band game exact.
    if(r==2) {
        bool stop=false;
        for(int i=0;i<c && !stop;++i) {
            if(cand[i].size+cand[std::min(i+1,c-1)].size<=best_score)break;
            for(int j=i+1;j<c;++j) {
                if(cand[i].size+cand[j].size<=best_score)break;
                int value=cand[i].size+gain(cand[j].cover,cand[i].cover);
                if(value>best_score)record({i,j},value);
                if(best_score==target){stop=true;break;}
            }
            if((i&15)==0 && elapsed(started)>budget*0.94)break;
        }
    } else {
        // Starting from each promising polygon avoids the first-choice bias of
        // ordinary maximum-coverage greedy. Randomized restarts and exchanges
        // spend the remaining budget on the genuinely ambiguous positions.
        int starts=std::min(c,96);
        for(int z=0;z<starts && best_score<target;++z) {
            if(elapsed(started)>budget*0.75)break;
            int initial=z<c/2?z:std::min(c-1,z*c/starts);
            improve(greedy({initial},0,rng));
        }
        for(int trial=0;trial<2000 && best_score<target;++trial) {
            if(elapsed(started)>budget*0.91)break;
            std::vector<int> seed;
            if(trial%3==0 && !best.empty()) {
                seed=best;
                int erase_count=std::min((int)seed.size(),2+trial%3);
                for(int e=0;e<erase_count;++e)seed.erase(seed.begin()+rng()%seed.size());
            }
            improve(greedy(std::move(seed),15+(trial%6)*20,rng));
        }
        // Two coordinated replacements escape coverage traps that no single
        // exchange can improve. Marginal-gain bounds skip almost all pairs.
        if(r>5 && best_score<target && elapsed(started)<budget*0.75) {
            for(int pass=0;pass<3 && best_score<target;++pass) {
                bool changed=false;
                for(size_t a=0;a<best.size() && elapsed(started)<budget*0.92;++a)
                for(size_t b=a+1;b<best.size() && elapsed(started)<budget*0.92;++b) {
                    Bits base(words,0);
                    for(size_t z=0;z<best.size();++z)if(z!=a && z!=b)unite(base,cand[best[z]].cover);
                    int base_score=count(base);
                    std::vector<std::pair<int,int>> options;
                    for(int j=0;j<c;++j){int g=gain(cand[j].cover,base);if(g)options.push_back({g,j});}
                    std::sort(options.rbegin(),options.rend());
                    if(options.size()>96)options.resize(96);
                    int value=best_score,ja=-1,jb=-1;
                    for(size_t u=0;u<options.size();++u) {
                        if(base_score+options[u].first+options[0].first<=value)break;
                        int i=options[u].second;
                        for(size_t v=u+1;v<options.size();++v) {
                            if(base_score+options[u].first+options[v].first<=value)break;
                            int j=options[v].second,score=base_score;
                            for(int w=0;w<words;++w)score+=__builtin_popcountll((cand[i].cover[w]|cand[j].cover[w])&~base[w]);
                            if(score>value){value=score;ja=i;jb=j;}
                        }
                    }
                    if(ja>=0){best[a]=ja;best[b]=jb;best_score=value;changed=true;}
                }
                if(!changed)break;
                improve(best);
            }
        }
        // Certify the optimum when only a few bands are available. Each node
        // is bounded by both the remaining union and the largest marginal
        // gains, and the shared deadline preserves the game clock.
        if(best_score<target && (r<=5 || c<=32) && elapsed(started)<budget*0.92) {
            std::vector<Bits> suffix(c+1,Bits(words,0));
            for(int j=c-1;j>=0;--j){suffix[j]=suffix[j+1];unite(suffix[j],cand[j].cover);}
            std::vector<int> selected;
            uint64_t nodes=0;
            bool timed_out=false;
            std::function<void(int,int,const Bits&,int)> search;
            search=[&](int start,int slots,const Bits& covered,int score) {
                if(timed_out || best_score==target)return;
                if((++nodes&255)==0 && elapsed(started)>budget*0.96){timed_out=true;return;}
                if(score>best_score)record(selected,score);
                if(slots==0 || start==c)return;
                if(score+gain(suffix[start],covered)<=best_score)return;
                std::vector<std::pair<int,int>> options;
                for(int j=start;j<c;++j){int g=gain(cand[j].cover,covered);if(g)options.push_back({g,j});}
                std::sort(options.rbegin(),options.rend());
                int bound=score;
                for(int z=0;z<slots && z<(int)options.size();++z)bound+=options[z].first;
                if(bound<=best_score)return;
                if(slots==1) {
                    selected.push_back(options[0].second);record(selected,score+options[0].first);selected.pop_back();return;
                }
                for(const auto& option:options) {
                    int j=option.second;
                    Bits next=covered;unite(next,cand[j].cover);
                    selected.push_back(j);search(j+1,slots-1,next,score+option.first);selected.pop_back();
                    if(timed_out || best_score==target)return;
                }
            };
            search(0,r,Bits(words,0),0);
        }
    }
    for(int j:best)result.bands.push_back(cand[j].hull);
    result.score=std::max(0,best_score);
    return result;
}

} // namespace pegband
#endif
