# A PegBand bot in Julia. Copy this folder to bots/<your-name>/ and write your strategy.
#
# The referee runs this program as a subprocess: one JSON message per line arrives on standard
# input, one JSON object per line goes back on standard output. Print to standard error for
# debugging. The referee ignores it.
#
# Squares are numbered 0 .. N*N-1, left to right and top to bottom: square i is in row i ÷ N
# and column i % N. Note these are 0-based, like the rest of the architecture.
#
# Messages you receive:
#   {"type":"start","color":"green","N":10,"pegs":5,"bands":5,"clock":120}
#       -> reply {"ready":true}.  This one is not on your clock.
#   {"type":"peg", ...}   -> reply {"peg":34}
#   {"type":"band", ...}  -> reply {"band":[12,34,56]}

# -- the smallest amount of JSON reading this bot needs -----------------------

"The integer that follows \"key\": in the message, or fallback when it is not there."
function field(line::String, key::String, fallback::Int=-1)
    m = match(Regex("\"" * key * "\":(-?\\d+)"), line)
    m === nothing ? fallback : parse(Int, m.captures[1])
end

"""The list of integers that follows \"key\": [ ... ].

Use this for the flat lists: `board`, `your_pegs`, `their_pegs`, `scores`. The band lists
(`your_bands`, `their_bands`) are lists OF lists, so read those with `list_of_lists`."""
function list_field(line::String, key::String)
    m = match(Regex("\"" * key * "\":\\[([^\\[\\]]*)\\]"), line)
    m === nothing && return Int[]
    body = strip(m.captures[1])
    isempty(body) && return Int[]
    [parse(Int, strip(x)) for x in split(body, ',') if !isempty(strip(x))]
end

"The list of lists that follows \"key\": [[...],[...]], used for your_bands and their_bands."
function list_of_lists(line::String, key::String)
    at = findfirst("\"" * key * "\":[", line)
    at === nothing && return Vector{Int}[]
    out = Vector{Int}[]
    depth = 0
    buf = IOBuffer()
    for ch in line[(last(at)):end]
        if ch == '['
            depth += 1
            depth == 2 && (buf = IOBuffer())
        elseif ch == ']'
            if depth == 2
                body = strip(String(take!(buf)))
                push!(out, isempty(body) ? Int[] :
                      [parse(Int, strip(x)) for x in split(body, ',') if !isempty(strip(x))])
            end
            depth -= 1
            depth == 0 && break
        elseif depth == 2
            write(buf, ch)
        end
    end
    out
end

has_type(line, what) = occursin("\"type\":\"$what\"", line)

# -----------------------------------------------------------------------------
# EDIT ONLY THIS SECTION
# -----------------------------------------------------------------------------

mutable struct Bot
    N::Int
    pegs::Int
    bands::Int
    Bot() = new(0, 0, 0)
end

function start!(bot::Bot, line::String)
    bot.N = field(line, "N", 10)
    bot.pegs = field(line, "pegs", 1)
    bot.bands = field(line, "bands", 1)
end

"Return the square to put your next peg on."
function place_peg(bot::Bot, line::String)
    taken = Set(vcat(list_field(line, "your_pegs"), list_field(line, "their_pegs")))
    for i in 0:(bot.N * bot.N - 1)
        i in taken || return i
    end
    return 0
end

"""Return the pegs of yours to stretch this rubberband around. The band is their convex hull,
so the order does not matter. It must not contain or touch an enemy peg."""
function place_band(bot::Bot, line::String)
    mine = list_field(line, "your_pegs")
    isempty(mine) ? Int[] : mine[1:1]
end

# -----------------------------------------------------------------------------
# Below here is the plumbing. You should not need to change it.
# -----------------------------------------------------------------------------

function main()
    bot = Bot()
    for line in eachline(stdin)
        isempty(strip(line)) && continue
        if has_type(line, "start")
            start!(bot, line)
            println("{\"ready\":true}")
        elseif has_type(line, "peg")
            println("{\"peg\":", place_peg(bot, line), "}")
        elseif has_type(line, "band")
            band = place_band(bot, line)
            println("{\"band\":[", join(band, ","), "]}")
        else
            println("{}")
        end
        flush(stdout)
    end
end

main()
